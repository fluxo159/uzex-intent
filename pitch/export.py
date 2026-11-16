import argparse
import json
import os
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

QR_URL = "https://demo.example/guest"

HERE = Path(__file__).resolve().parent
NUMBERS = HERE.parent / "docs" / "pitch_numbers.json"
PAGES = 9
MAX_MB = 15
W, H = 1920, 1080

def write_data_js() -> dict:
    data = json.loads(NUMBERS.read_text(encoding="utf-8"))
    (HERE / "data.js").write_text(
        "// Сгенерировано pitch/export.py из docs/pitch_numbers.json — руками не править.\n"
        "window.PITCH = " + json.dumps(data, ensure_ascii=False, indent=1) + ";\n",
        encoding="utf-8",
    )
    return data

def write_qr(url: str) -> None:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_M

    q = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=24, border=4)
    q.add_data(url)
    q.make(fit=True)
    img = q.make_image(fill_color="#080909", back_color="#C7FA58")
    img.save(HERE / "qr.png")
    (HERE / "qr.js").write_text(
        "// Сгенерировано pitch/export.py — адрес в QR.\nwindow.PITCH_QR = " + json.dumps(url) + ";\n",
        encoding="utf-8",
    )

def render(shots: bool) -> Path:
    from playwright.sync_api import sync_playwright

    pdf = HERE / "pitch.pdf"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1, reduced_motion="reduce")
        page.goto((HERE / "index.html").as_uri())
        page.wait_for_selector("html[data-ready='1']")
        page.evaluate("async () => { await Promise.all([...document.fonts].map(f => f.load())); await document.fonts.ready; }")
        page.wait_for_timeout(300)

        missing = page.eval_on_selector_all(".missing", "els => els.map(e => e.getAttribute('data-n'))")
        if missing:
            sys.exit(f"Нет в pitch_numbers.json: {missing}")

        cdp = page.context.new_cdp_session(page)
        cdp.send("DOM.enable")
        cdp.send("CSS.enable")
        root = cdp.send("DOM.getDocument", {"depth": -1})["root"]
        fallback = set()
        for nid in cdp.send("DOM.querySelectorAll", {"nodeId": root["nodeId"], "selector": ".slide *"})["nodeIds"]:
            for f in cdp.send("CSS.getPlatformFontsForNode", {"nodeId": nid})["fonts"]:
                if not f["isCustomFont"]:
                    fallback.add(f["familyName"])
        if fallback:
            sys.exit(f"Часть текста набрана системным шрифтом: {sorted(fallback)}")

        overflow = page.evaluate(
            """() => {
              const bad = [];
              document.querySelectorAll('.slide').forEach(s => {
                const r0 = s.getBoundingClientRect();
                s.querySelectorAll('*').forEach(el => {
                  const r = el.getBoundingClientRect();
                  if (!r.width || !r.height) return;
                  const k = r0.width / 1920;
                  const out = (r.left - r0.left) / k < -1 || (r.top - r0.top) / k < -1 ||
                              (r.right - r0.left) / k > 1921 || (r.bottom - r0.top) / k > 1081;
                  const clip = el.scrollWidth > el.clientWidth + 2 && getComputedStyle(el).overflow !== 'visible'
                               && !el.classList.contains('th');
                  if (out || clip) bad.push(s.id + ' ' + el.tagName.toLowerCase() + '.' + el.className + ' «' + (el.textContent || '').trim().slice(0, 30) + '»');
                });
              });
              return bad;
            }"""
        )
        if overflow:
            print("ВНИМАНИЕ, выход за край / обрезка:")
            for b in overflow:
                print("  ", b)

        page.add_style_tag(content="*{animation:none!important}")
        if shots:
            out = HERE / "shots"
            out.mkdir(exist_ok=True)
            for old in out.glob("p*.png"):
                old.unlink()
            for i in range(1, PAGES + 1):
                page.evaluate(f"window.scrollTo(0, {(i - 1) * H})")
                page.wait_for_timeout(50)
                page.screenshot(path=str(out / f"p{i:02d}.png"))
            page.evaluate("window.scrollTo(0, 0)")

        page.emulate_media(media="print")
        page.pdf(
            path=str(pdf), width=f"{W}px", height=f"{H}px", print_background=True,
            prefer_css_page_size=True, margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        )
        browser.close()
    return pdf

def check_pdf(pdf: Path) -> None:
    raw = pdf.read_bytes()
    mb = len(raw) / 1024 / 1024
    try:
        from pypdf import PdfReader

        r = PdfReader(str(pdf))
        pages = len(r.pages)
        box = r.pages[0].mediabox
        size = f"{float(box.width):.0f}×{float(box.height):.0f} pt"
        embedded = set()

        def fonts_of(res, seen):
            res = res.get_object() if res else {}
            for f in (res.get("/Font") or {}).values():
                yield f.get_object()
            for x in (res.get("/XObject") or {}).values():
                x = x.get_object()
                if id(x) not in seen:
                    seen.add(id(x))
                    yield from fonts_of(x.get("/Resources"), seen)

        for pg in r.pages:
            for f in fonts_of(pg.get("/Resources"), set()):
                desc = f.get("/FontDescriptor")
                if desc is None and "/DescendantFonts" in f:
                    desc = f["/DescendantFonts"][0].get_object().get("/FontDescriptor")
                if f.get("/Subtype") == "/Type3" and "/CharProcs" in f:
                    embedded.add("Type3 (контуры глифов)")
                elif desc is not None:
                    d = desc.get_object()
                    if any(k in d for k in ("/FontFile", "/FontFile2", "/FontFile3")):
                        embedded.add(str(f.get("/BaseFont")).split("+")[-1])
    except ImportError:
        pages = len(re.findall(rb"/Type\s*/Page[^s]", raw))
        size = "?"
        embedded = {"(pypdf нет — проверка по байтам)"} if b"/FontFile" in raw else set()
    print(f"pitch.pdf: {pages} стр., {mb:.2f} МБ, страница {size}")
    print("встроенные шрифты:", ", ".join(sorted(embedded)) or "НЕТ")
    ok = pages == PAGES and mb < MAX_MB and embedded
    if not ok:
        sys.exit("Проверка PDF не прошла")
    print("OK")

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--qr", default=os.environ.get("PITCH_QR_URL", QR_URL))
    ap.add_argument("--shots", action="store_true")
    a = ap.parse_args()
    write_data_js()
    write_qr(a.qr)
    print("QR →", a.qr)
    for attempt in range(3):
        try:
            pdf = render(a.shots)
            break
        except Exception as e:  # noqa: BLE001
            if attempt == 2 or "closed" not in str(e).lower():
                raise
            print("chromium упал при старте, повтор…")
    check_pdf(pdf)

if __name__ == "__main__":
    main()
