#!/usr/bin/env python
"""
Load test runner script for SummarEase.

Usage:
    python loadtest/run_load_test.py --scenario steady
    python loadtest/run_load_test.py --scenario stress --host http://staging.example.com
    python loadtest/run_load_test.py --scenario spike --headless
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

SCENARIOS = {
    "steady": {"users": 10, "spawn_rate": 2, "duration": "5m"},
    "stress": {"users": 50, "spawn_rate": 5, "duration": "5m"},
    "spike": {"users": 100, "spawn_rate": 20, "duration": "2m"},
    "soak": {"users": 20, "spawn_rate": 2, "duration": "30m"},
}


def run_locust(scenario: str, host: str, headless: bool, html_report: str = None, users: int = None, spawn_rate: int = None, duration: str = None):
    """Run locust with given parameters."""
    config = SCENARIOS.get(scenario, {})
    users = users or config.get("users", 10)
    spawn_rate = spawn_rate or config.get("spawn_rate", 2)
    duration = duration or config.get("duration", "5m")

    locustfile = Path(__file__).parent / "locustfile.py"
    if not locustfile.exists():
        print(f"❌ Locustfile not found: {locustfile}")
        return 1

    cmd = [
        "locust",
        "-f", str(locustfile),
        "--host", host,
        "-u", str(users),
        "-r", str(spawn_rate),
        "-t", duration,
    ]

    if headless:
        cmd.append("--headless")

    if html_report:
        cmd.extend(["--html", html_report])

    print(f"🚀 Running Locust: {' '.join(cmd)}")
    print(f"   Scenario: {scenario}")
    print(f"   Users: {users}, Spawn rate: {spawn_rate}, Duration: {duration}")
    print(f"   Target: {host}")
    print()

    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"❌ Locust failed with exit code {e.returncode}")
        return e.returncode
    except FileNotFoundError:
        print("❌ Locust not installed. Run: pip install locust")
        return 1


def main():
    parser = argparse.ArgumentParser(description="Run SummarEase load tests")
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()),
        default="steady",
        help="Load test scenario"
    )
    parser.add_argument(
        "--host",
        default=os.getenv("LOCUST_HOST", "http://localhost:8000"),
        help="Target host URL"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode (no web UI)"
    )
    parser.add_argument(
        "--html-report",
        help="Path to save HTML report"
    )
    parser.add_argument(
        "-u", "--users",
        type=int,
        help="Number of users (overrides scenario default)"
    )
    parser.add_argument(
        "-r", "--spawn-rate",
        type=int,
        help="Spawn rate (users/second, overrides scenario default)"
    )
    parser.add_argument(
        "-t", "--duration",
        help="Test duration (e.g., 5m, 30s, 1h, overrides scenario default)"
    )

    args = parser.parse_args()

    return run_locust(
        scenario=args.scenario,
        host=args.host,
        headless=args.headless,
        html_report=args.html_report,
        users=args.users,
        spawn_rate=args.spawn_rate,
        duration=args.duration,
    )


if __name__ == "__main__":
    sys.exit(main())