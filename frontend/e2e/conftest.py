import os
import pytest
import requests
import time
from playwright.sync_api import Playwright, APIRequestContext

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


# Playwright configuration
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test requiring running server"
    )


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session", autouse=True)
def ensure_server_running(base_url):
    """Ensure the Django server is running before tests."""
    max_retries = 30
    for i in range(max_retries):
        try:
            resp = requests.get(f"{base_url}/health/", timeout=2)
            if resp.status_code in (200, 503):
                return
        except Exception:
            pass
        time.sleep(1)
    pytest.fail(f"Server at {base_url} did not become ready in time")


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args, base_url):
    return {
        **browser_context_args,
        "base_url": base_url,
        "ignore_https_errors": True,
    }