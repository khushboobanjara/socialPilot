from app.core.security import hash_password, verify_password, create_access_token, decode_access_token

def test_password_hash_round_trip():
    stored = hash_password("StrongPassword123")
    assert stored != "StrongPassword123"
    assert verify_password("StrongPassword123", stored)
    assert not verify_password("WrongPassword123", stored)

def test_jwt_round_trip():
    token = create_access_token("42")
    assert decode_access_token(token) == "42"
