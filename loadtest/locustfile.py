"""
Locust load test for SummarEase API endpoints.

Run with:
    locust -f loadtest/locustfile.py --host=http://localhost:8000

Or headless:
    locust -f loadtest/locustfile.py --host=http://localhost:8000 --headless -u 10 -r 2 -t 60s --html=report.html
"""

import os
import json
import random
import string
from locust import HttpUser, task, between, events


BASE_URL = os.getenv("LOCUST_HOST", "http://localhost:8000")


def random_text(length=500):
    """Generate random text for testing."""
    words = [
        "trí tuệ nhân tạo", "học máy", "xử lý ngôn ngữ tự nhiên", "tóm tắt văn bản",
        "TextRank", "Gemini", "Google", "mô hình ngôn ngữ", "học sâu", "mạng nơ-ron",
        "dữ liệu", "thuật toán", "máy tính", "khoa học dữ liệu", "phân tích",
        "nghiên cứu", "phát triển", "ứng dụng", "công nghệ", "tương lai"
    ]
    return " ".join(random.choices(words, k=length // 10)) + "."


class SummarEaseUser(HttpUser):
    """Simulated user for SummarEase."""

    wait_time = between(1, 3)  # Wait 1-3 seconds between requests

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.csrf_token = None
        self.session_id = None
        self.authenticated = False

    def on_start(self):
        """Initialize user session."""
        # Get CSRF token from home page
        with self.client.get("/", catch_response=True) as response:
            if response.status_code == 200:
                # Extract CSRF token from cookies or form
                self.csrf_token = response.cookies.get("csrftoken")
                if not self.csrf_token:
                    # Try to find in HTML
                    import re
                    match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', response.text)
                    if match:
                        self.csrf_token = match.group(1)
            else:
                response.failure(f"Home page failed: {response.status_code}")

    @task(5)
    def view_home(self):
        """View home page."""
        with self.client.get("/", name="Home Page", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Home page failed: {response.status_code} - {response.text[:200]}")

    @task(3)
    def view_health(self):
        """View health endpoint."""
        with self.client.get("/health/", name="Health Check", catch_response=True) as response:
            if response.status_code not in (200, 503):
                response.failure(f"Health check failed: {response.status_code} - {response.text[:200]}")
            elif response.status_code == 200:
                try:
                    data = response.json()
                    if "status" not in data:
                        response.failure("Health response missing status")
                except json.JSONDecodeError:
                    response.failure(f"Health response not valid JSON: {response.text[:200]}")

    @task(2)
    def view_metrics(self):
        """View Prometheus metrics endpoint."""
        with self.client.get("/metrics/", name="Metrics", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Metrics failed: {response.status_code} - {response.text[:200]}")

    @task(1)
    def view_api_docs(self):
        """View API documentation."""
        with self.client.get("/api/docs/", name="Swagger UI", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Swagger UI failed: {response.status_code}")

    @task(1)
    def view_redoc(self):
        """View ReDoc documentation."""
        with self.client.get("/api/redoc/", name="ReDoc", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"ReDoc failed: {response.status_code}")

    @task(1)
    def view_schema(self):
        """View OpenAPI schema."""
        with self.client.get("/api/schema/", name="OpenAPI Schema", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Schema failed: {response.status_code}")


class AuthenticatedUser(SummarEaseUser):
    """Authenticated user with login."""

    def on_start(self):
        super().on_start()
        self.login()

    def login(self):
        """Login as test user."""
        # Create/register a test user first
        username = f"loadtest_{random.randint(1000, 9999)}"
        password = "LoadTest123!"

        # Try to register
        with self.client.post(
            "/register/",
            data={
                "username": username,
                "password1": password,
                "password2": password,
                "csrfmiddlewaretoken": self.csrf_token or "",
            },
            name="Register",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 302):
                self.authenticated = True
            elif "already exists" in response.text:
                # User might already exist, try login
                self.authenticated = True
            else:
                response.failure(f"Registration failed: {response.status_code}")

        # Login
        if self.authenticated:
            with self.client.post(
                "/login/",
                data={
                    "username": username,
                    "password": password,
                    "csrfmiddlewaretoken": self.csrf_token or "",
                },
                name="Login",
                catch_response=True,
            ) as response:
                if response.status_code in (200, 302):
                    self.authenticated = True
                else:
                    self.authenticated = False
                    response.failure(f"Login failed: {response.status_code}")

    @task(10)
    def create_summary_text(self):
        """Create summary from text (authenticated)."""
        if not self.authenticated:
            return

        text = random_text(random.randint(200, 2000))
        ratio = random.choice([0.1, 0.2, 0.3, 0.4, 0.5])
        method = random.choice(["textrank", "gemini"])

        with self.client.post(
            "/create-summary/",
            data={
                "source_type": "text",
                "text": text,
                "method": method,
                "ratio": ratio,
                "csrfmiddlewaretoken": self.csrf_token or "",
            },
            headers={"X-Requested-With": "XMLHttpRequest"},
            name="Create Summary (Text)",
            catch_response=True,
        ) as response:
            if response.status_code == 429:
                response.failure("Rate limited")
            elif response.status_code == 400:
                try:
                    data = response.json()
                    if "errors" in data:
                        response.failure(f"Validation errors: {data['errors']}")
                    else:
                        response.failure(f"Bad request: {data.get('message', 'Unknown')}")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code != 200:
                response.failure(f"Summary creation failed: {response.status_code}")
            else:
                try:
                    data = response.json()
                    if not data.get("ok"):
                        response.failure(f"API error: {data.get('message', 'Unknown')}")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")

    @task(5)
    def create_summary_url(self):
        """Create summary from URL (authenticated)."""
        if not self.authenticated:
            return

        urls = [
            "https://vnexpress.net/giao-duc/du-hoc-sinh-viet-nam-tang-manh-4721234.html",
            "https://tuoitre.vn/cong-nghe/ai-se-thay-the-con-nguoi-trong-tuong-lai-20240101.htm",
            "https://thanhnien.vn/khoa-hoc-cong-nghe/tri-tue-nhan-tao-va-tuong-lai-1852345.html",
        ]

        with self.client.post(
            "/create-summary/",
            data={
                "source_type": "url",
                "source_url": random.choice(urls),
                "method": "textrank",
                "ratio": 0.3,
                "csrfmiddlewaretoken": self.csrf_token or "",
            },
            headers={"X-Requested-With": "XMLHttpRequest"},
            name="Create Summary (URL)",
            catch_response=True,
        ) as response:
            if response.status_code == 429:
                response.failure("Rate limited")
            elif response.status_code != 200:
                # URL extraction might fail, that's OK for load test
                response.failure(f"URL summary failed: {response.status_code}")


class AnonymousUser(SummarEaseUser):
    """Anonymous user (no authentication)."""

    @task(8)
    def view_home_anon(self):
        """View home page as anonymous."""
        self.view_home()

    @task(4)
    def view_health_anon(self):
        """View health as anonymous."""
        self.view_health()

    @task(2)
    def view_metrics_anon(self):
        """View metrics as anonymous."""
        self.view_metrics()

    @task(1)
    def attempt_summary_anon(self):
        """Anonymous user sees login prompt instead of form submit."""
        with self.client.get("/", name="Home (Anonymous)", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Home failed: {response.status_code}")
            elif "Đăng nhập để tóm tắt" not in response.text:
                response.failure("Anonymous login prompt not found")


# Event hooks for reporting
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print(f"\nStarting load test against {BASE_URL}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print(f"\nLoad test completed")
    stats = environment.stats
    print(f"Total Requests: {stats.total.num_requests}")
    print(f"Failures: {stats.total.num_failures}")
    print(f"Avg Response Time: {stats.total.avg_response_time:.0f}ms")
    print(f"Max Response Time: {stats.total.max_response_time:.0f}ms")
    print(f"Requests/sec: {stats.total.total_rps:.2f}")

    if stats.total.num_failures > 0:
        print(f"\nFailure rate: {stats.total.num_failures / max(stats.total.num_requests, 1) * 100:.1f}%")
        for name, stat in stats.entries.items():
            if stat.num_failures > 0:
                print(f"  {name}: {stat.num_failures} failures ({stat.fail_ratio*100:.1f}%)")


# Custom user classes for different load profiles
class LightUser(AuthenticatedUser):
    """Light user - fewer requests, longer waits."""
    wait_time = between(3, 8)


class HeavyUser(AuthenticatedUser):
    """Heavy user - more requests, shorter waits."""
    wait_time = between(0.5, 1.5)


class SpikeUser(HttpUser):
    """Spike testing - burst of requests."""
    wait_time = between(0.1, 0.5)

    @task
    def burst_home(self):
        self.client.get("/", name="Burst Home")


# Load shape for different scenarios
class LoadShape:
    """Define load shape for different test scenarios."""

    # Steady load: 10 users, 2 spawn rate, 5 min duration
    STEADY = {"users": 10, "spawn_rate": 2, "duration": "5m"}

    # Stress test: ramp to 50 users over 2 min, hold 3 min
    STRESS = {"users": 50, "spawn_rate": 5, "duration": "5m"}

    # Spike test: quick burst to 100 users
    SPIKE = {"users": 100, "spawn_rate": 20, "duration": "2m"}

    # Soak test: 20 users for 30 min
    SOAK = {"users": 20, "spawn_rate": 2, "duration": "30m"}