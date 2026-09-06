import os
from playwright.sync_api import Playwright

# Playwright configuration
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test requiring running server"
    )


# Playwright settings
def pytest_playwright_configure(playwright: Playwright):
    # This is called once per test session
    pass


# Test timeout
TEST_TIMEOUT = 30000

# Browser launch options
BROWSER_LAUNCH_OPTIONS = {
    "headless": os.getenv("HEADLESS", "true").lower() == "true",
    "slow_mo": int(os.getenv("SLOW_MO", "0")),
    "args": ["--no-sandbox", "--disable-dev-shm-usage"],
}

# Context options
CONTEXT_OPTIONS = {
    "viewport": {"width": 1280, "height": 720},
    "ignore_https_errors": True,
    "base_url": BASE_URL,
}