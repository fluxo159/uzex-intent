from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .. import config

REGISTRY_FILE = "registry_mock.json"
DEMO_LABEL = "ДЕМО: в проде — реестр налоговой"

class RegistryUnavailable(Exception):
    pass

@lru_cache(maxsize=1)
def _load(path: str | None = None) -> dict[str, dict]:
    p = Path(path) if path else config.DATA_DEMO / REGISTRY_FILE
    data = json.loads(p.read_text(encoding="utf-8"))
    return {str(e["inn"]): e for e in data["entities"]}

def lookup(inn: str | None, down: bool = False) -> dict | None:
    if down:
        raise RegistryUnavailable("реестр недоступен")
    if not inn:
        return None
    try:
        return _load().get(str(inn).strip())
    except FileNotFoundError as e:
        raise RegistryUnavailable("нет файла реестра") from e

def mask_inn(inn: str | None) -> str | None:
    if not inn:
        return None
    s = str(inn)
    return "*" * max(0, len(s) - 3) + s[-3:]

def entities() -> list[dict]:
    return list(_load().values())
