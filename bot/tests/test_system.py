import pytest
import os
from bot.services.system_service import SystemService

@pytest.fixture
def system_service():
    os.environ['ALLOWED_SERVICES'] = 'nginx,docker'
    return SystemService()

def test_sanitize_filename(system_service):
    # Should strip dangerous characters
    assert system_service.sanitize_filename("my file.txt") == "my_file.txt"
    assert system_service.sanitize_filename("../../../etc/passwd") == "unnamed_file" # Since it starts with .
    assert system_service.sanitize_filename("good_file-123.jpg") == "good_file-123.jpg"

def test_is_service_allowed(system_service):
    assert system_service.is_service_allowed("nginx") is True
    assert system_service.is_service_allowed("docker") is True
    assert system_service.is_service_allowed("ssh") is False
