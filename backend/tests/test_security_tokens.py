from app.core.security import create_access_token, create_refresh_token, decode_access_token, decode_token


def test_access_token_rejects_refresh_typ():
    refresh = create_refresh_token({"sub": "1", "role": "participant"}, family_id="family-1")
    assert decode_access_token(refresh) is None


def test_access_token_round_trip():
    token = create_access_token({"sub": "7", "username": "alice", "role": "participant"})
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "7"
    assert payload["typ"] == "access"


def test_refresh_token_contains_family():
    token = create_refresh_token({"sub": "9"}, family_id="fam-xyz")
    payload = decode_token(token)
    assert payload is not None
    assert payload["typ"] == "refresh"
    assert payload["fam"] == "fam-xyz"
