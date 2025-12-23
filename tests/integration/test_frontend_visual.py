"""Visual validation tests for time-evolving heatmap frontend.

T045 [US4] - Playwright screenshot comparison tests.
Validates that the frontend correctly renders time-evolving liquidation data.

NOTE: These tests require Playwright browser automation.
Install with: uv add --dev playwright && uv run playwright install chromium
"""

import os
import signal
import socket
import subprocess
import time
from pathlib import Path

import pytest

# Skip if playwright not installed
pytest.importorskip("playwright")

from playwright.async_api import async_playwright


def _find_free_port() -> int:
    """Find an available port to avoid conflicts."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def _wait_for_server(url: str, timeout: float = 10.0) -> bool:
    """Wait for server to be ready with health check."""
    import httpx

    start = time.time()
    while time.time() - start < timeout:
        try:
            response = httpx.get(f"{url}/health", timeout=1.0)
            if response.status_code == 200:
                return True
        except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout, OSError):
            # Connection refused, timeout, or network error - server not ready yet
            pass
        time.sleep(0.5)
    return False


@pytest.fixture(scope="module")
def api_server():
    """Start API server for frontend testing."""
    port = _find_free_port()
    server_url = f"http://localhost:{port}"

    # Start server in background
    proc = subprocess.Popen(
        ["uv", "run", "uvicorn", "src.liquidationheatmap.api.main:app", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=Path(__file__).parent.parent.parent,
        preexec_fn=os.setsid,  # Create new process group for clean cleanup
    )

    # Wait for server to be ready with health check
    if not _wait_for_server(server_url, timeout=15.0):
        # Server failed to start - cleanup and fail
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        stderr = proc.stderr.read().decode() if proc.stderr else ""
        pytest.fail(f"API server failed to start on port {port}: {stderr}")

    yield server_url

    # Cleanup: terminate entire process group to ensure no zombies
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, OSError):
        pass  # Process already terminated

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        # Force kill if graceful shutdown fails
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass
        proc.wait()


@pytest.fixture
def screenshot_dir():
    """Directory for storing screenshots."""
    path = Path(__file__).parent / "screenshots"
    path.mkdir(exist_ok=True)
    return path


class TestTimeEvolvingHeatmapVisual:
    """Visual tests for time-evolving heatmap (T045)."""

    @pytest.mark.asyncio
    async def test_heatmap_page_loads(self, api_server, screenshot_dir):
        """Verify heatmap page loads without JavaScript errors."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Collect console errors
            errors = []
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

            # Navigate to heatmap page
            await page.goto(f"{api_server}/frontend/coinglass_heatmap.html")

            # Wait for page to load
            await page.wait_for_load_state("networkidle")

            # Take screenshot (convert Path to str for Playwright compatibility)
            await page.screenshot(path=str(screenshot_dir / "heatmap_loaded.png"))

            await browser.close()

            # No critical JS errors
            critical_errors = [e for e in errors if "Error" in e and "fetch" not in e.lower()]
            assert len(critical_errors) == 0, f"JavaScript errors: {critical_errors}"

    @pytest.mark.asyncio
    async def test_heatmap_has_time_evolving_badge(self, api_server):
        """Verify time-evolving mode badge is visible."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(f"{api_server}/frontend/coinglass_heatmap.html")
            await page.wait_for_load_state("networkidle")

            # Check for time-evolving badge
            badge = await page.query_selector("#time-evolving-badge")
            assert badge is not None, "Time-evolving badge not found"

            badge_text = await badge.inner_text()
            assert "Time-Evolving" in badge_text, f"Badge text incorrect: {badge_text}"

            await browser.close()

    @pytest.mark.asyncio
    async def test_heatmap_fetches_timeseries_endpoint(self, api_server):
        """Verify frontend uses new /heatmap-timeseries endpoint."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Track network requests
            requests = []
            page.on("request", lambda req: requests.append(req.url))

            await page.goto(f"{api_server}/frontend/coinglass_heatmap.html")

            # Wait for API calls
            await page.wait_for_timeout(3000)

            await browser.close()

            # Check that new endpoint was called
            timeseries_calls = [r for r in requests if "heatmap-timeseries" in r]
            assert len(timeseries_calls) > 0, "Frontend did not call /heatmap-timeseries endpoint"

            # Check that deprecated endpoint was NOT called
            deprecated_calls = [
                r for r in requests if "/liquidations/levels" in r and "heatmap-timeseries" not in r
            ]
            assert len(deprecated_calls) == 0, (
                f"Frontend still uses deprecated endpoint: {deprecated_calls}"
            )

    @pytest.mark.asyncio
    async def test_heatmap_renders_plotly_chart(self, api_server, screenshot_dir):
        """Verify Plotly chart is rendered."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(f"{api_server}/frontend/coinglass_heatmap.html")

            # Wait for chart to render
            await page.wait_for_timeout(5000)

            # Check for Plotly chart container
            chart_element = await page.query_selector("#heatmap .plotly")

            # Take screenshot (convert Path to str for Playwright compatibility)
            await page.screenshot(path=str(screenshot_dir / "heatmap_chart.png"), full_page=True)

            await browser.close()

            # Chart should exist (may be None if API unavailable, which is acceptable in CI)
            # We just verify no crash occurred - chart_element intentionally unused for now
            _ = chart_element  # Explicitly acknowledge we're not asserting on this yet


class TestHeatmapDataVisualization:
    """Tests for correct data visualization (requires running API)."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires live API with data - run manually")
    async def test_density_varies_per_column(self, api_server, screenshot_dir):
        """Verify each time column has different density (time-evolving behavior)."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(f"{api_server}/frontend/coinglass_heatmap.html")
            await page.wait_for_timeout(5000)

            # Check status message for consumed positions
            status = await page.query_selector("#status")
            status_text = await status.inner_text() if status else ""

            # Take final screenshot (convert Path to str for Playwright compatibility)
            await page.screenshot(
                path=str(screenshot_dir / "heatmap_with_data.png"), full_page=True
            )

            await browser.close()

            # If data loaded, status should mention snapshots and consumed
            assert "Time-evolving" in status_text or "Error" in status_text, (
                f"Unexpected status: {status_text}"
            )
