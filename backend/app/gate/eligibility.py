from __future__ import annotations

from typing import Any

from . import funds as funds_mod
from . import registry

COMMODITY_ALIASES = {
    "cement": "cement", "цемент": "cement", "sement": "cement",
    "cotton": "cotton", "хлопок": "cotton", "paxta": "cotton", "пахта": "cotton",
    "lpg": "lpg", "суг": "lpg", "сжиженный газ": "lpg", "suyultirilgan gaz": "lpg",
}

PERSON_2035_TEXT = ("Модель 2035: сегодня по п. 4 Правил клиентами могут быть только юрлица и ИП; "
                    "прецедент — РФБ \"Тошкент\" §7-1 (2019)")
REGION_TEXT = "покупка в другом регионе: по п. 105 Правил поставка по месту регистрации; в демо разрешено"
DOWN_TEXT = "проверка недоступна, повторим перед торгами"
GUEST_TEXT = ("ДЕМО-участник: вход по QR на показе, без ИНН; в проде — вход ИП/компании по E-IMZO "
              "или частного лица по ID-карте (модель 2035)")
NO_REGISTRY_KINDS = ("person_2035", "guest")
PERSON_DEMO_BALANCE = 50_000_000

def _chk(name: str, level: str, reason: str, how_to_fix: str | None = None, **extra: Any) -> dict:
    return {"name": name, "passed": level != "blocked", "level": level, "reason": reason,
            "how_to_fix": how_to_fix, **extra}

def normalize_commodity(c: str | None) -> str:
    return COMMODITY_ALIASES.get(str(c or "cement").strip().lower(), str(c or "").strip().lower())

def check(principal: dict, line_items: list[dict], funds_available: int | None = None,
          registry_down: bool = False) -> dict:
    kind = (principal.get("kind") or principal.get("principal_kind") or "").strip()
    inn = principal.get("inn")
    region = principal.get("region")
    checks: list[dict] = []

    if kind in ("ip", "company"):
        checks.append(_chk("principal_kind", "ok", "ИП и юрлица допускаются по сегодняшним Правилам"))
    elif kind == "person_2035":
        checks.append(_chk("principal_kind", "warning", PERSON_2035_TEXT, model_2035=True))
    elif kind == "guest":
        checks.append(_chk("principal_kind", "warning", GUEST_TEXT, demo=True, guest=True))
    else:
        checks.append(_chk("principal_kind", "blocked", f"неизвестный вид участника «{kind}»",
                           "выберите «Я ИП или фирма» или «Я частное лицо»"))

    entity = None
    down = False
    if kind == "person_2035":
        checks.append(_chk("company_status", "ok", "частное лицо: проверка по ID-карте (ДЕМО)", demo=True))
    elif kind == "guest":
        checks.append(_chk("company_status", "ok", "ДЕМО-участник: без проверки по реестру", demo=True))
    else:
        try:
            entity = registry.lookup(inn, down=registry_down)
            if entity is None:
                checks.append(_chk("company_status", "blocked", "ИНН не найден в реестре", "проверьте ИНН",
                                   demo=True))
            elif entity.get("status") == "active":
                checks.append(_chk("company_status", "ok", "активна", demo=True, entity_name=entity.get("name")))
            else:
                checks.append(_chk("company_status", "blocked", "деятельность приостановлена",
                                   "восстановить статус в налоговой", demo=True, entity_name=entity.get("name")))
        except registry.RegistryUnavailable:
            down = True
            checks.append(_chk("company_status", "warning", DOWN_TEXT, demo=True))
    if entity and not region:
        region = entity.get("region")

    for it in line_items:
        c = normalize_commodity(it.get("commodity"))
        if c == "cement":
            checks.append(_chk("commodity_right", "ok", "цемент: без ограничений", commodity=c))
        elif c == "cotton":
            if down:
                checks.append(_chk("commodity_right", "warning", DOWN_TEXT, commodity=c))
            elif entity and entity.get("cotton_processor") and entity.get("hokimiyat_recommendation"):
                checks.append(_chk("commodity_right", "ok", "хлопок: в списке переработчиков, рекомендация хокимията есть",
                                   commodity=c))
            elif entity and entity.get("cotton_processor"):
                checks.append(_chk("commodity_right", "blocked", "хлопок: нет рекомендации хокимията",
                                   "получить рекомендацию хокимията", commodity=c))
            else:
                checks.append(_chk("commodity_right", "blocked", "хлопок: нет в списке переработчиков",
                                   "получить рекомендацию хокимията", commodity=c))
        elif c == "lpg":
            if down:
                checks.append(_chk("commodity_right", "warning", DOWN_TEXT, commodity=c))
            elif entity and entity.get("lpg_license"):
                checks.append(_chk("commodity_right", "ok", "СУГ: лицензия в ИС «Лицензия» есть", commodity=c))
            else:
                checks.append(_chk("commodity_right", "blocked", "СУГ: нет лицензии в ИС «Лицензия»",
                                   "получить лицензию в ИС «Лицензия»", commodity=c))
        else:
            checks.append(_chk("commodity_right", "blocked", f"товар «{it.get('commodity')}» не поддержан в демо",
                               "выберите цемент", commodity=c))

    fa = funds_available
    if fa is None and entity is not None:
        fa = entity.get("demo_balance")
    if fa is None and kind in NO_REGISTRY_KINDS:
        fa = PERSON_DEMO_BALANCE
    try:
        checks.append(funds_mod.check(fa, line_items))
    except (KeyError, ValueError) as e:
        checks.append(_chk("funds", "blocked", f"нельзя посчитать задаток: {e}", "укажите объём и цену"))

    for it in line_items:
        allowed = it.get("allowed_regions") or []
        if allowed and region and allowed[0] != region:
            checks.append(_chk("region_rule", "warning", REGION_TEXT, delivery_region=allowed[0],
                               registration_region=region))
    if not any(c["name"] == "region_rule" for c in checks):
        checks.append(_chk("region_rule", "ok", "поставка в регион регистрации"))

    levels = {c["level"] for c in checks}
    status = "blocked" if "blocked" in levels else "warning" if "warning" in levels else "ok"
    return {"status": status, "checks": checks, "demo": True, "demo_label": registry.DEMO_LABEL,
            "inn_masked": registry.mask_inn(inn), "region": region}
