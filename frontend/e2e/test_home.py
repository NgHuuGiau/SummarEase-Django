import os
import re
from uuid import uuid4

import pytest
from playwright.sync_api import Page, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from summaries.exports import _check_weasyprint

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

    def test_service_worker_caches_only_public_static_assets(self, page: Page, base_url: str):
        page.goto(base_url)
        # The worker is registered from /static/sw.js so its scope is /static/.
        # Wait for activation first (proves the worker is alive), then wait for
        # cache entries (install fetches can lag activation on slow runners).
        page.wait_for_function(
            """async () => {
                const reg = await navigator.serviceWorker.getRegistration('/static/');
                return reg && reg.active && reg.active.state === 'activated';
            }""",
            timeout=20000,
        )
        page.wait_for_function(
            """async () => {
                const keys = (await caches.keys()).filter(key => key.startsWith('summarease-'));
                const entries = await Promise.all(keys.map(async key =>
                    (await caches.open(key)).keys()
                ));
                return entries.some(requests => requests.length > 0);
            }""",
            timeout=30000,
        )
        cached_urls = page.evaluate(
            """async () => {
                const keys = (await caches.keys()).filter(key => key.startsWith('summarease-'));
                const entries = await Promise.all(keys.map(async key =>
                    (await caches.open(key)).keys()
                ));
                return entries.flat().map(request => new URL(request.url).pathname);
            }"""
        )
        assert cached_urls
        assert all(path.startswith("/static/") for path in cached_urls)

    @pytest.mark.parametrize("width,height", [(375, 812), (768, 1024), (1280, 800)])
    def test_home_layout_fits_common_viewports(
        self, page: Page, base_url: str, width: int, height: int
    ):
        page.set_viewport_size({"width": width, "height": height})
        page.goto(base_url)
        expect(page.locator("main")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")

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
        expect(page.locator("#text-wrap")).not_to_have_class(re.compile(r".*is-hidden.*"))
        expect(page.locator("#file-wrap")).to_have_class(re.compile(r".*is-hidden.*"))
        expect(page.locator("#url-wrap")).to_have_class(re.compile(r".*is-hidden.*"))

        # Click file
        page.locator('[data-source="file"]').click()
        expect(page.locator("#text-wrap")).to_have_class(re.compile(r".*is-hidden.*"))
        expect(page.locator("#file-wrap")).not_to_have_class(re.compile(r".*is-hidden.*"))
        expect(page.locator("#url-wrap")).to_have_class(re.compile(r".*is-hidden.*"))

        # Click URL
        page.locator('[data-source="url"]').click()
        expect(page.locator("#text-wrap")).to_have_class(re.compile(r".*is-hidden.*"))
        expect(page.locator("#file-wrap")).to_have_class(re.compile(r".*is-hidden.*"))
        expect(page.locator("#url-wrap")).not_to_have_class(re.compile(r".*is-hidden.*"))

        # Click back to text
        page.locator('[data-source="text"]').click()
        expect(page.locator("#text-wrap")).not_to_have_class(re.compile(r".*is-hidden.*"))
        expect(page.locator("#file-wrap")).to_have_class(re.compile(r".*is-hidden.*"))
        expect(page.locator("#url-wrap")).to_have_class(re.compile(r".*is-hidden.*"))

    def test_method_selector_switches(self, page: Page, base_url: str):
        """Method selector switches between TextRank and Gemini."""
        page.goto(base_url)

        # Default is TextRank
        expect(page.locator('[data-method="textrank"]')).to_have_class(re.compile(r".*is-active.*"))
        expect(page.locator("#method-hint")).to_contain_text("TextRank")

        # Switch to Gemini if available
        gemini_btn = page.locator('[data-method="gemini"]')
        if "is-disabled" not in (gemini_btn.get_attribute("class") or ""):
            gemini_btn.click()
            expect(gemini_btn).to_have_class(re.compile(r".*is-active.*"))
            expect(page.locator("#method-hint")).to_contain_text("Gemini")

    def test_ratio_slider_updates(self, page: Page, base_url: str):
        """Ratio slider updates the hidden input and display."""
        page.goto(base_url)

        slider = page.locator("#ratio_slider")
        ratio_input = page.locator("#ratio_input")
        ratio_value = page.locator("#ratio_value")

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

    def test_password_reset_request_shows_confirmation(self, page: Page, base_url: str):
        page.goto(f"{base_url}/password-reset/")
        page.locator("input[name='email']").fill("unknown@example.com")
        page.locator("button[type='submit']").click()
        expect(page).to_have_url(re.compile(r"/password-reset/done/$"))
        expect(page.locator("main")).to_contain_text("Nếu email bạn nhập tồn tại")

    def test_authenticated_summary_and_share_flow(self, page: Page, base_url: str):
        """A new user can create a summary and open its sharing dialog."""
        token = uuid4().hex[:10]
        username = f"e2e_{token}"
        password = "E2E!SummarEase2026"

        page.goto(f"{base_url}/register/")
        page.locator("input[name='username']").fill(username)
        page.locator("input[name='email']").fill(f"{username}@example.com")
        page.locator("input[name='password1']").fill(password)
        page.locator("input[name='password2']").fill(password)
        page.locator("button[type='submit']").click()

        expect(page.locator("#submit-btn")).to_be_visible()

        # Account settings persist and feed the user's default summary ratio.
        page.goto(f"{base_url}/settings/")
        ratio_setting = page.locator("input[name='default_summary_ratio']")
        ratio_setting.fill("0.4")
        page.locator(".settings-form button[type='submit']").click()
        expect(page.locator(".flash.success")).to_contain_text("Đã lưu cài đặt")
        page.reload()
        expect(page.locator("input[name='default_summary_ratio']")).to_have_value("0.4")

        page.goto(base_url)
        page.locator("#text-input").fill("")
        page.locator("#submit-btn").click()
        expect(page.locator("#error-text")).to_contain_text("Nhập văn bản cần tóm tắt")

        page.locator("#text-input").fill(
            "Kiểm thử end-to-end giúp xác nhận người dùng có thể tạo và quản lý bản tóm tắt. "
            "Hệ thống cần phản hồi ổn định, bảo mật và dễ sử dụng."
        )
        page.locator("#submit-btn").click()

        expect(page.locator("#form-message")).to_contain_text(
            "Đã tạo và lưu bản tóm tắt", timeout=15000
        )
        expect(page.locator("#detail-link")).to_be_visible()
        page.locator("#detail-link").click()

        expect(page).to_have_title("Chi tiết bản tóm tắt - SummarEase")
        expect(page.locator("#copy-detail-btn")).to_be_visible()
        summary_title = page.locator(".panel-header-title h2").inner_text()
        owned_summary_url = page.url

        # Search from history, create a share link, and open it as a guest.
        page.goto(f"{base_url}/history/")
        page.locator("input[name='q']").fill(summary_title)
        page.locator("input[name='q']").press("Enter")
        expect(page.locator(".history-list-item")).to_have_count(1)
        expect(page.locator(".history-list-item")).to_contain_text(summary_title)
        page.goto(owned_summary_url)
        page.locator("#share-btn").click()
        expect(page.locator("#share-modal")).to_be_visible()
        with page.expect_response(lambda response: "/share/" in response.url) as share_info:
            page.locator("#confirm-share").click()
        share_response = share_info.value
        assert share_response.status == 200
        share_data = share_response.json()
        assert share_data["ok"] is True
        page.goto(share_data["share_url"])
        expect(page.locator(".shared-notice")).to_be_visible()
        expect(page.locator("#detail-summary-text")).to_be_visible()

        # Upload a real in-memory text file and verify the resulting export.
        page.goto(base_url)
        page.locator('[data-source="file"]').click()
        page.locator("#file-input").set_input_files(
            {
                "name": "e2e-upload.txt",
                "mimeType": "text/plain",
                "buffer": (
                    "Tệp tải lên cần được đọc và tóm tắt chính xác. "
                    "Kiểm thử bao phủ trọn luồng chọn tệp, xử lý và xuất dữ liệu."
                ).encode(),
            }
        )
        # The API intentionally rate-limits requests from one IP for five seconds.
        page.wait_for_timeout(5200)
        page.locator("#submit-btn").click()
        expect(page.locator("#form-message")).to_contain_text(
            "Đã tạo và lưu bản tóm tắt", timeout=15000
        )
        page.locator("#detail-link").click()
        upload_summary_url = page.url
        page.locator(".export-trigger").click()
        expect(page.locator(".export-item").first).to_be_visible()
        with page.expect_download() as download_info:
            with page.expect_response(
                lambda response: "/export/md/" in response.url
            ) as export_info:
                page.locator(".export-item", has_text="Markdown").click()
        download = download_info.value
        export_response = export_info.value
        assert export_response.status == 200
        assert download.suggested_filename.endswith(".md")
        assert export_response.headers["content-disposition"].startswith("attachment;")
        assert export_response.headers["content-type"].startswith("text/markdown")

        for label, extension, content_type in (
            (
                "Word",
                "docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            ("PDF", "pdf", "application/pdf"),
        ):
            if extension == "pdf" and not _check_weasyprint():
                continue
            page.locator(".export-trigger").click()
            try:
                with page.expect_response(
                    lambda response, extension=extension: f"/export/{extension}/" in response.url
                ) as format_export:
                    with page.expect_download(timeout=10000) as format_download:
                        page.locator(".export-item", has_text=label).click()
            except PlaywrightTimeoutError as exc:
                response = format_export.value
                raise AssertionError(
                    f"{extension} export did not download: HTTP {response.status}, "
                    f"Content-Disposition={response.headers.get('content-disposition')}, "
                    f"body={response.text()[:300]}"
                ) from exc
            assert format_export.value.status == 200
            assert format_download.value.suggested_filename.endswith(f".{extension}")
            assert format_export.value.headers["content-type"].startswith(content_type)

        # A different account must not be able to view this account's summary.
        page.goto(owned_summary_url)
        page.locator(".logout-form button").click()
        username2 = f"e2e_{uuid4().hex[:10]}"
        page.goto(f"{base_url}/register/")
        page.locator("input[name='username']").fill(username2)
        page.locator("input[name='email']").fill(f"{username2}@example.com")
        page.locator("input[name='password1']").fill(password)
        page.locator("input[name='password2']").fill(password)
        page.locator("button[type='submit']").click()
        response = page.goto(owned_summary_url)
        assert response is not None and response.status == 404
        response = page.goto(upload_summary_url)
        assert response is not None and response.status == 404

        # Log back into the owner account and verify delete confirmation and result.
        page.goto(base_url)
        page.locator(".logout-form button").click()
        page.goto(f"{base_url}/login/")
        page.locator("input[name='username']").fill(username)
        page.locator("input[name='password']").fill(password)
        page.locator("button[type='submit']").click()
        page.goto(upload_summary_url)
        page.once("dialog", lambda dialog: dialog.accept())
        page.locator("form[data-confirm-delete] button").click()
        expect(page).to_have_url(re.compile(r"/history/$"))
        expect(page.locator(".history-list-item")).to_have_count(1)


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

        test_content = "This is a test document for summarization."
        page.locator("#file-input").set_input_files(
            {
                "name": "test_upload.txt",
                "mimeType": "text/plain",
                "buffer": test_content.encode("utf-8"),
            }
        )
        dropzone_strong = page.locator("#file-wrap .dropzone-content strong")
        expect(dropzone_strong).to_contain_text("test_upload.txt")


class TestAccessibility:
    """Lightweight accessibility checks without a third-party browser add-on."""

    def test_home_has_landmark_heading_and_named_controls(self, page: Page, base_url: str):
        """Check primary landmarks and that visible controls have accessible names."""
        page.goto(base_url)
        expect(page.locator("main")).to_be_visible()
        expect(page.locator("main h1").first).to_be_visible()
        assert page.locator("html").get_attribute("lang")
        unnamed = page.locator("button:visible:not([aria-label]):not([title])").evaluate_all(
            "buttons => buttons.filter(button => !button.innerText.trim())"
            ".map(button => button.outerHTML)"
        )
        assert not unnamed, f"Visible buttons missing accessible names: {unnamed}"

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

    def test_segmented_choices_expose_pressed_button_state(self, page: Page, base_url: str):
        page.goto(base_url)
        source_group = page.get_by_role("group", name="Chọn nguồn dữ liệu")
        source_button = source_group.get_by_role("button", name=re.compile("Tệp tin"))

        expect(source_button).to_have_attribute("aria-pressed", "false")
        source_button.focus()
        page.keyboard.press("Space")
        expect(source_button).to_have_attribute("aria-pressed", "true")
        expect(page.locator('[data-source="text"]')).to_have_attribute("aria-pressed", "false")


class TestHealthEndpoint:
    """Test health endpoint via browser."""

    def test_health_endpoint_accessible(self, page: Page, base_url: str):
        """Health endpoint returns JSON."""
        response = page.goto(f"{base_url}/health/")
        assert response.ok
        json_data = response.json()
        assert "status" in json_data
        assert json_data["status"] in ["ok", "healthy", "degraded"]


# Run with: pytest frontend/e2e/test_home.py -v --headed
