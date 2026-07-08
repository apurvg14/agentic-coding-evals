"""Shared fixtures for the dashboard test suite.

Two ways the tests find a dashboard to talk to:

- If AGENTEVAL_DASHBOARD_URL is set (e.g. in Docker, pointing at the compose
  `dashboard` service), the tests target that already-running server.
- Otherwise a dashboard subprocess is started on a free port, writing results to
  a throwaway temp directory so real results/ is never touched.

The `page` fixture is only needed by the Playwright E2E tests; if Playwright
isn't installed the browser fixture skips those tests but the API tests (which
use only the stdlib) still run.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
READY_TIMEOUT = float(os.environ.get("AGENTEVAL_READY_TIMEOUT", "60"))


def pytest_configure(config):
    # Register markers here too, so they work even when pytest.ini isn't present
    # (e.g. the Docker test runner mounts only tests/ into the container).
    config.addinivalue_line(
        "markers", "e2e: browser-based end-to-end tests (require Playwright + a browser)")


def _wait_ready(base_url: str, timeout: float = READY_TIMEOUT) -> None:
    deadline = time.time() + timeout
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base_url + "/api/meta", timeout=3) as r:
                if r.status == 200:
                    return
        except Exception as e:  # noqa: BLE001 - server may not be up yet
            last_err = e
        time.sleep(0.4)
    raise RuntimeError(f"dashboard never became ready at {base_url}: {last_err}")


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="session")
def base_url():
    """A base URL for a live dashboard, cleaned up afterwards if we started it."""
    env_url = os.environ.get("AGENTEVAL_DASHBOARD_URL")
    if env_url:
        env_url = env_url.rstrip("/")
        _wait_ready(env_url)
        yield env_url
        return

    port = _free_port()
    tmp = tempfile.mkdtemp(prefix="agenteval-test-results-")
    env = os.environ.copy()
    env["AGENTEVAL_RESULTS_DIR"] = tmp
    proc = subprocess.Popen(
        [sys.executable, "-m", "agenteval", "dashboard",
         "--host", "127.0.0.1", "--port", str(port), "--no-open"],
        cwd=str(ROOT), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        _wait_ready(url)
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:  # noqa: BLE001
            proc.kill()


@pytest.fixture(scope="session")
def browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("playwright not installed (pip install -r requirements-dev.txt)")
    pw = sync_playwright().start()
    try:
        br = pw.chromium.launch()
    except Exception as e:  # noqa: BLE001 - browser binaries missing
        pw.stop()
        pytest.skip(f"chromium unavailable (run `playwright install chromium`): {e}")
    yield br
    br.close()
    pw.stop()


@pytest.fixture
def page(browser):
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    pg = context.new_page()
    yield pg
    context.close()
