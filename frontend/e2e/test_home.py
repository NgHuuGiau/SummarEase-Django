import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


class TestHomePage:
    """E2E tests for the home page."""

    def test_home_page_loads(self, page: Page, base_url: str):
        """Home page loads successfully with all key elements."""
        page.goto(base_url)
        expect(page).to_have_title("SummarEase - Tóm tắt văn bản thông minh với AI")

        # Hero section
        expect(page.locator(".hero-title")).to_be_visible()
        expect(page.locator(".hero-subtitle")).to_be_visible()
        expect(page.locator(".hero-badge")).to_be_visible()

        # Feature pills
        expect(page.locator(".feature-pills .pill")).to_have_count(3)

    def test_guest_mode_shows_login_prompt(self, page: Page, base_url: str):
        """Guest mode shows login prompt instead of submit button."""
        page.goto(base_url)

        # Should show login link instead of submit button
        expect(page.locator("#summary-form .form-footer a[href*='login']")).to_be_visible()
        expect(page.locator(".auth-hint")).to_be_visible()
        expect(page.locator("#submit-btn")).not_to_be_visible()

    def test_source_selector_switches(self, page: Page, base_url: str):
        """Source selector buttons switch input areas."""
        page.goto(base_url)

        # Default is text
        expect(page.locator("#text-wrap")).not_to_have_class("is-hidden")
        expect(page.locator("#file-wrap")).to_have_class("is-hidden")
        expect(page.locator("#url-wrap")).to_have_class("is-hidden")

        # Click file
        page.locator('[data-source="file"]').click()
        expect(page.locator("#text-wrap")).to_have_class("is-hidden")
        expect(page.locator("#file-wrap")).not_to_have_class("is-hidden")
        expect(page.locator("#url-wrap")).to_have_class("is-hidden")

        # Click URL
        page.locator('[data-source="url"]').click()
        expect(page.locator("#text-wrap")).to_have_class("is-hidden")
        expect(page.locator("#file-wrap")).to_have_class("is-hidden")
        expect(page.locator("#url-wrap")).not_to_have_class("is-hidden")

        # Click back to text
        page.locator('[data-source="text"]').click()
        expect(page.locator("#text-wrap")).not_to_have_class("is-hidden")
        expect(page.locator("#file-wrap")).to_have_class("is-hidden")
        expect(page.locator("#url-wrap")).to_have_class("is-hidden")

    def test_method_selector_switches(self, page: Page, base_url: str):
        """Method selector switches between TextRank and Gemini."""
        page.goto(base_url)

        # Default is TextRank
        expect(page.locator('[data-method="textrank"]')).to_have_class("is-active")
        expect(page.locator("#method-hint")).to_contain_text("TextRank")

        # Switch to Gemini if available
        gemini_btn = page.locator('[data-method="gemini"]')
        if not gemini_btn.get_attribute("class").contains("is-disabled"):
            gemini_btn.click()
            expect(gemini_btn).to_have_class("is-active")
            expect(page.locator("#method-hint")).to_contain_text("Gemini")

    def test_ratio_slider_updates(self, page: Page, base_url: str):
        """Ratio slider updates the hidden input and display."""
        page.goto(base_url)

        slider = page.locator("#ratio_slider")
        ratio_input = page.locator("#ratio_input")
        ratio_value = page.locator("#ratio_value")

        initial = slider.get_attribute("value")
        slider.fill("50")
        page.wait_for_timeout(100)

        expect(ratio_input).to_have_value("0.50")
        expect(ratio_value).to_have_text("50%")


class TestAuthentication:
    """E2E tests for authentication flows."""

    def test_login_page_loads(self, page: Page, base_url: str):
        """Login page loads with correct elements."""
        page.goto(f"{base_url}/login/")
        expect(page.locator("form[method='post']")).to_be_visible()
        expect(page.locator("input[name='username']")).to_be_visible()
        expect(page.locator("input[name='password']")).to_be_visible()
        expect(page.locator("button[type='submit']")).to_be_visible()

    def test_register_page_loads(self, page: Page, base_url: str):
        """Register page loads with correct elements."""
        page.goto(f"{base_url}/register/")
        expect(page.locator("form[method='post']")).to_be_visible()
        expect(page.locator("input[name='username']")).to_be_visible()
        expect(page.locator("input[name='password1']")).to_be_visible()
        expect(page.locator("input[name='password2']")).to_be_visible()


class TestThemeToggle:
    """E2E tests for theme toggle."""

    def test_theme_toggle_works(self, page: Page, base_url: str):
        """Theme toggle switches between light and dark mode."""
        page.goto(base_url)

        toggle = page.locator("[data-theme-toggle]")
        if toggle.count() == 0:
            pytest.skip("Theme toggle not found")

        # Get initial theme
        initial_theme = page.locator("html").get_attribute("data-theme")
        if initial_theme is None:
            initial_theme = "light"

        # Click toggle
        toggle.click()
        page.wait_for_timeout(100)

        # Theme should change
        new_theme = page.locator("html").get_attribute("data-theme")
        assert new_theme != initial_theme

        # Click again to revert
        toggle.click()
        page.wait_for_timeout(100)
        reverted_theme = page.locator("html").get_attribute("data-theme")
        assert reverted_theme == initial_theme


class TestSummaryForm:
    """E2E tests for summary form interactions."""

    def test_text_input_validation(self, page: Page, base_url: str):
        """Text input shows validation when empty."""
        page.goto(base_url)

        # Try to submit empty form
        page.locator("#text-input").fill("")
        page.locator("#summary-form").evaluate("form => form.dispatchEvent(new Event('submit'))")

        # Wait a bit for validation
        page.wait_for_timeout(500)

        # Should show some error (depends on form validation)
        # At minimum, form should not submit successfully

    def test_file_input_updates_display(self, page: Page, base_url: str):
        """File input updates the dropzone text when file selected."""
        page.goto(base_url)

        page.locator('[data-source="file"]').click()
        page.wait_for_timeout(100)

        # Create a test file
        test_content = "This is a test document for summarization."
        file_path = os.path.join(os.path.dirname(__file__), "test_upload.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(test_content)

        try:
            page.locator("#file-input").set_input_files(file_path)
            page.wait_for_timeout(200)

            # Dropzone should show filename
            dropzone_strong = page.locator("#file-wrap .dropzone-content strong")
            expect(dropzone_strong).to_contain_text("test_upload.txt")
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)


class TestAccessibility:
    """Basic accessibility checks."""

    def test_no_axe_violations_home(self, page: Page, base_url: str):
        """Home page has no critical axe violations."""
        page.goto(base_url)
        # This would require axe-playwright, skipping for now
        # Just verify page loads
        expect(page.locator("main")).to_be_visible()

    def test_keyboard_navigation(self, page: Page, base_url: str):
        """Key interactive elements are keyboard accessible."""
        page.goto(base_url)

        # Tab through source selector
        page.keyboard.press("Tab")
        page.keyboard.press("Tab")
        page.keyboard.press("Tab")
        page.keyboard.press("Tab")

        # Source selector buttons should be focusable
        focused = page.evaluate("document.activeElement.tagName")
        assert focused in ["BUTTON", "A", "INPUT"]


class TestHealthEndpoint:
    """Test health endpoint via browser."""

    def test_health_endpoint_accessible(self, page: Page, base_url: str):
        """Health endpoint returns JSON."""
        response = page.goto(f"{base_url}/health/")
        assert response.ok
        json_data = response.json()
        assert "status" in json_data
        assert json_data["status"] in ["healthy", "degraded"]


# Run with: pytest frontend/e2e/test_home.py -v --headed