from __future__ import annotations

import argparse
import html
import secrets
from pathlib import Path

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

def code(n: int = 8) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(n))

def cards_html(codes: list[str], site: str) -> str:
    cells = "\n".join(
        f'<div class="card"><div class="t">UZEX · Биржа намерений</div><div class="c">{c[:4]}-{c[4:]}</div>'
        f'<div class="h">«Ещё → Код доступа» или {html.escape(site)}/?k={c}</div>'
        f'<div class="h">«Yana → Kirish kodi»</div></div>' for c in codes)
    return f"""<!doctype html><meta charset="utf-8"><title>Коды жюри</title>
<style>body{{font-family:system-ui,sans-serif;margin:12mm}}.g{{display:grid;grid-template-columns:repeat(2,1fr);gap:6mm}}
.card{{border:1px dashed #888;border-radius:4mm;padding:6mm;break-inside:avoid}}.t{{font-size:11pt;color:#555}}
.c{{font:700 26pt ui-monospace,monospace;letter-spacing:2pt;margin:3mm 0}}.h{{font-size:9pt;color:#333}}</style>
<div class="g">{cells}</div>"""

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--len", type=int, default=8, choices=range(6, 9))
    ap.add_argument("--html", type=Path, help="записать карточки для печати")
    ap.add_argument("--site", default="https://demo.example")
    a = ap.parse_args()
    codes: list[str] = []
    while len(codes) < a.n:
        c = code(a.len)
        if c not in codes:
            codes.append(c)
    print("# --- в .env сервера ---")
    print("JURY_CODES=" + ",".join(codes))
    print("ADMIN_TOKEN=" + secrets.token_urlsafe(24))
    print("AUTH_SECRET=" + secrets.token_urlsafe(32))
    print("# --- коды для карточек ---")
    for i, c in enumerate(codes, 1):
        print(f"{i:2}. {c[:4]}-{c[4:]}")
    if a.html:
        a.html.write_text(cards_html(codes, a.site), encoding="utf-8")
        print(f"# карточки: {a.html}")

if __name__ == "__main__":
    main()
