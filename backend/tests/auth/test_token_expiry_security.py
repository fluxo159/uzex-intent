import base64
import json
import pytest
from app.auth import tokens

@pytest.mark.parametrize("expiry", [None, {}, [], "not-a-number"])
def test_signed_malformed_expiry_is_rejected(expiry):
    body = base64.urlsafe_b64encode(json.dumps({"exp": expiry}).encode()).rstrip(b"=").decode()
    token = body + "." + tokens._mac(body, "access")
    assert tokens.verify(token, "access") is None
