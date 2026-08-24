import pytest
import os
import time
from bot.services.auth_service import AuthService

@pytest.fixture
def auth_service():
    os.environ['LOGIN_MAX_FAILS'] = '3'
    os.environ['LOGIN_LOCKOUT_MINUTES'] = '10'
    return AuthService()

def test_hash_password(auth_service):
    pwd = "my_secure_password"
    hashed = auth_service.hash_password(pwd)
    assert hashed != pwd
    assert auth_service.check_password(pwd, hashed) is True
    assert auth_service.check_password("wrong", hashed) is False
