from __future__ import annotations

class EimzoAdapter:
    def sign(self, doc_hash: str) -> dict:  # pragma: no cover - не подключено
        raise NotImplementedError("в проде: eimzo-client на десктопе, PKCS#7 над хешем поручения")
