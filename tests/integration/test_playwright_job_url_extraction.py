"""Optional local-browser integration test for Playwright extraction."""

from urllib.parse import quote

import pytest

from app.features.job_url_extraction.extractors import PlaywrightJobExtractor
from app.models.enums import SourcePlatform

HTML = """
<!doctype html>
<html>
  <head><title>Backend Engineer - Platform Labs</title></head>
  <body>
    <h1>Backend Engineer</h1>
    <div>Platform Labs</div>
    <div>Remote</div>
    <main>
      We are hiring a backend engineer to build reliable Python APIs,
      FastAPI services, PostgreSQL integrations, and automation workflows.
    </main>
  </body>
</html>
"""


@pytest.mark.browser
def test_extracts_local_data_url_with_installed_chromium() -> None:
    """Exercise a real Chromium page without touching an external job site."""
    extractor = PlaywrightJobExtractor()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"data:text/html,{quote(HTML)}")
        result = extractor.extract_from_page(
            page,
            job_url="https://careers.example.com/jobs/backend",
            platform=SourcePlatform.UNKNOWN,
        )
        browser.close()

    assert result.pipeline_ready
    assert result.raw_title == "Backend Engineer"
    assert result.company_name == "Platform Labs"
