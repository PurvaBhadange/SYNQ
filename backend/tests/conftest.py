"""
Pytest configuration and global test fixtures for SYNQ backend test suite.
"""

import pytest_asyncio
from config import get_settings
from db.session import init_db

settings = get_settings()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_environment():
    """Ensure database schema is fully migrated and test environment configured."""
    # Temporarily set app_env to test for pytest execution
    original_env = settings.app_env
    settings.app_env = "test"
    await init_db()
    yield
    settings.app_env = original_env


import pytest
from core.middleware import rate_limiter

@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Reset rate limiter state before and after each test."""
    rate_limiter.reset_for_tests()
    yield
    rate_limiter.reset_for_tests()

