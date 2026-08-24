import pytest
import os
import time
from bot.services.rate_limit import RateLimiter

def test_rate_limiter():
    os.environ['COMMAND_RATE_LIMIT'] = '3'
    os.environ['COMMAND_RATE_WINDOW'] = '1'

    limiter = RateLimiter()
    user_id = 123

    assert limiter.is_rate_limited(user_id) is False # 1
    assert limiter.is_rate_limited(user_id) is False # 2
    assert limiter.is_rate_limited(user_id) is False # 3
    assert limiter.is_rate_limited(user_id) is True  # 4 (limited)

    time.sleep(1.1)

    assert limiter.is_rate_limited(user_id) is False # Should be clear now
