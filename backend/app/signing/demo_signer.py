from __future__ import annotations

import datetime as dt
import hashlib
import hmac

from .. import config

ALG = "HMAC-SHA256 (ДЕМО)"
_KEY = hashlib.sha256(f"uzex-intent-demo-{config.DEMO_SEED}".encode()).digest()

def sign(doc_hash: str, signed_at: dt.datetime, signer: str = "principal") -> dict:
    if not doc_hash or len(doc_hash) != 64:
        raise ValueError("подписывается sha256-хеш поручения (64 hex)")
    mac = hmac.new(_KEY, f"{doc_hash}|{signed_at.isoformat()}|{signer}".encode(), hashlib.sha256).hexdigest()
    return {"receipt_id": "RC-" + mac[:10].upper(), "hash": doc_hash, "signed_at": signed_at.isoformat(),
            "signer": signer, "alg": ALG, "mac": mac, "demo": True,
            "prod_note": "в проде: E-IMZO, ID-карта (PKCS#7)"}

def verify(receipt: dict) -> bool:
    try:
        exp = sign(receipt["hash"], dt.datetime.fromisoformat(receipt["signed_at"]), receipt.get("signer", "principal"))
    except (KeyError, ValueError):
        return False
    return hmac.compare_digest(exp["mac"], receipt.get("mac", ""))
