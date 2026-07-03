"""Playwright-backed user-authorized single-URL job extraction."""

from __future__ import annotations

import re
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from app.models.enums import SourcePlatform
from app.schemas.job_url_extraction import JobUrlExtractionRequest, JobUrlExtractionResult

from .base import BaseJobUrlExtractor

BLOCKED_PAGE_MARKERS = (
    "captcha",
    "verify you are human",
    "access denied",
    "unusual traffic",
    "sign in to continue",
    "log in to continue",
    "login required",
    "authentication required",
)

LOGIN_PAGE_MARKERS = (
    "sign in with apple",
    "email or phone",
    "forgot password",
    "keep me logged in",
    "new to linkedin",
    "join linkedin",
)

BLOCKED_URL_PATH_MARKERS = (
    "/authwall",
    "/checkpoint/",
    "/login",
    "/uas/login",
)

NOISE_LINES = {
    "about",
    "accessibility",
    "careers",
    "cookies",
    "help",
    "home",
    "jobs",
    "privacy",
    "sign in",
    "terms",
}

PLATFORM_SELECTORS: dict[SourcePlatform, dict[str, tuple[str, ...]]] = {
    SourcePlatform.LINKEDIN: {
        "raw_title": (
            ".top-card-layout__title",
            ".job-details-jobs-unified-top-card__job-title",
        ),
        "company_name": (
            ".topcard__org-name-link",
            ".job-details-jobs-unified-top-card__company-name",
        ),
        "location": (
            ".topcard__flavor--bullet",
            ".job-details-jobs-unified-top-card__primary-description-container",
        ),
        "description_text": (
            ".show-more-less-html__markup",
            ".jobs-description__content",
        ),
    },
    SourcePlatform.INDEED: {
        "raw_title": ("h1[data-testid='jobsearch-JobInfoHeader-title']", "h1"),
        "company_name": (
            "[data-testid='inlineHeader-companyName']",
            "[data-company-name='true']",
        ),
        "location": (
            "[data-testid='job-location']",
            "[data-testid='inlineHeader-companyLocation']",
        ),
        "description_text": ("#jobDescriptionText",),
    },
    SourcePlatform.GLASSDOOR: {
        "raw_title": ("[data-test='job-title']", "h1"),
        "company_name": ("[data-test='employer-name']",),
        "location": ("[data-test='location']",),
        "description_text": ("[data-test='job-description']", ".JobDetails_jobDescription__"),
    },
}

DOMAIN_SELECTORS: dict[str, dict[str, tuple[str, ...]]] = {
    "greenhouse.io": {
        "raw_title": ("h1.app-title", ".job__title h1", "h1"),
        "company_name": (".company-name", ".job__company"),
        "location": (".location", ".job__location"),
        "description_text": ("#content", ".job__description", ".content"),
    },
    "lever.co": {
        "raw_title": (".posting-headline h2", "h2"),
        "company_name": (".posting-headline .company", ".company-name"),
        "location": (".posting-categories .location", ".location"),
        "description_text": (
            ".posting-page .content",
            ".posting-description",
            ".section-wrapper.page-full-width",
        ),
    },
}

UNSUPPORTED_PLATFORM_WARNING = (
    "Unsupported job platform. Please paste the job description manually."
)


class PlaywrightJobExtractor(BaseJobUrlExtractor):
    """Extract visible job fields from one URL using a read-only Chromium page."""

    def extract(self, request: JobUrlExtractionRequest) -> JobUrlExtractionResult:
        """Open one page, read visible content, and return practical v1 extraction."""
        platform = self.detect_platform(request.job_url)
        if platform == SourcePlatform.UNKNOWN:
            return self.failure_result(
                request.job_url,
                platform,
                UNSUPPORTED_PLATFORM_WARNING,
            )
        timeout_ms = request.timeout_seconds * 1000
        navigation_url = self.normalize_job_url(request.job_url)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=request.headless)
                page = browser.new_page()
                try:
                    page.goto(
                        navigation_url,
                        wait_until="domcontentloaded",
                        timeout=timeout_ms,
                    )
                    page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 5000))
                except PlaywrightTimeoutError:
                    pass
                try:
                    return self.extract_from_page(
                        page,
                        job_url=request.job_url,
                        platform=platform,
                    )
                finally:
                    browser.close()
        except Exception as exc:
            return self.failure_result(
                request.job_url,
                platform,
                f"Playwright extraction failed: {exc}. Use manual import fallback.",
            )

    def extract_from_page(
        self,
        page: Page,
        *,
        job_url: str,
        platform: SourcePlatform | None = None,
    ) -> JobUrlExtractionResult:
        """Extract visible content from an already-open Playwright page."""
        detected_platform = platform or self.detect_platform(job_url)
        visible_text = page.locator("body").inner_text()
        fields = self._selector_fields(page, detected_platform, job_url)
        return self.extract_from_visible_text(
            job_url=job_url,
            visible_text=visible_text,
            page_title=page.title(),
            final_url=page.url,
            platform=detected_platform,
            selector_fields=fields,
        )

    def extract_from_visible_text(
        self,
        *,
        job_url: str,
        visible_text: str,
        page_title: str = "",
        final_url: str = "",
        platform: SourcePlatform | None = None,
        selector_fields: dict[str, str | None] | None = None,
    ) -> JobUrlExtractionResult:
        """Infer job fields from visible text for browser and unit-test use."""
        detected_platform = platform or self.detect_platform(job_url)
        cleaned_text = self.clean_visible_text(visible_text)
        warnings = self.blocked_page_warnings(
            cleaned_text,
            page_title=page_title,
            final_url=final_url,
        )
        if warnings:
            warnings.append("Use manual import fallback for this posting.")
            return self.failure_result(job_url, detected_platform, *warnings)
        fields = selector_fields or {}
        title = fields.get("raw_title") or self.infer_title(page_title, cleaned_text)
        company = fields.get("company_name") or self.infer_company(page_title, cleaned_text, title)
        location = fields.get("location") or self.infer_location(cleaned_text, title, company)
        description = fields.get("description_text") or cleaned_text
        if not title:
            warnings.append("Job title could not be inferred from visible page content.")
        if not company:
            warnings.append("Company name could not be inferred from visible page content.")
        if len(description) < 80:
            warnings.append("Visible job-description text is too short for reliable analysis.")
        pipeline_ready = bool(title and company and len(description) >= 80)
        confidence = self._confidence(
            title=title,
            company=company,
            location=location,
            description=description,
            selector_fields=fields,
        )
        return JobUrlExtractionResult(
            job_url=job_url,
            detected_platform=detected_platform,
            raw_title=title,
            company_name=company,
            location=location,
            description_text=description,
            employment_type=self.infer_employment_type(cleaned_text),
            workplace_type=self.infer_workplace_type(cleaned_text),
            extraction_confidence=confidence,
            extraction_warnings=warnings,
            pipeline_ready=pipeline_ready,
        )

    @staticmethod
    def detect_platform(job_url: str) -> SourcePlatform:
        """Detect a supported source from the provided URL domain."""
        domain = (urlparse(job_url).hostname or "").casefold()
        if domain == "linkedin.com" or domain.endswith(".linkedin.com"):
            return SourcePlatform.LINKEDIN
        if domain == "indeed.com" or domain.endswith(".indeed.com"):
            return SourcePlatform.INDEED
        if domain == "glassdoor.com" or domain.endswith(".glassdoor.com"):
            return SourcePlatform.GLASSDOOR
        if domain == "greenhouse.io" or domain.endswith(".greenhouse.io"):
            return SourcePlatform.COMPANY_SITE
        if domain == "lever.co" or domain.endswith(".lever.co"):
            return SourcePlatform.COMPANY_SITE
        return SourcePlatform.UNKNOWN

    @staticmethod
    def normalize_job_url(job_url: str) -> str:
        """Convert LinkedIn search links with a current job ID into direct job URLs."""
        parsed = urlparse(job_url)
        domain = (parsed.hostname or "").casefold()
        if domain == "linkedin.com" or domain.endswith(".linkedin.com"):
            current_job_id = parse_qs(parsed.query).get("currentJobId", [""])[0].strip()
            if current_job_id.isdigit():
                return f"https://www.linkedin.com/jobs/view/{current_job_id}"
        return job_url

    @staticmethod
    def clean_visible_text(visible_text: str) -> str:
        """Remove obvious navigation noise and normalize visible page text."""
        lines = []
        seen: set[str] = set()
        for raw_line in visible_text.splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip()
            key = line.casefold()
            if not line or key in NOISE_LINES or key in seen:
                continue
            seen.add(key)
            lines.append(line)
        return "\n".join(lines)

    @staticmethod
    def blocked_page_warnings(
        visible_text: str,
        *,
        page_title: str = "",
        final_url: str = "",
    ) -> list[str]:
        """Return safe-stop warnings for login walls, CAPTCHAs, and blocked pages."""
        normalized = visible_text.casefold()
        markers = [marker for marker in BLOCKED_PAGE_MARKERS if marker in normalized]
        title = page_title.casefold()
        final_path = urlparse(final_url).path.casefold()
        login_marker_count = sum(marker in normalized for marker in LOGIN_PAGE_MARKERS)
        is_login_page = (
            "linkedin login" in title
            or login_marker_count >= 2
            or any(marker in final_path for marker in BLOCKED_URL_PATH_MARKERS)
        )
        if not markers and not is_login_page:
            return []
        if is_login_page:
            return [
                "The job site showed a login page instead of the job posting. "
                "Paste the job description manually."
            ]
        return [
            "Extraction stopped because the page appears blocked, gated, or requires verification."
        ]

    @staticmethod
    def infer_title(page_title: str, visible_text: str) -> str | None:
        """Infer a job title from the HTML title or first useful visible line."""
        title = _title_part(page_title)
        if title:
            return title
        return _first_line(visible_text)

    @staticmethod
    def infer_company(page_title: str, visible_text: str, raw_title: str | None) -> str | None:
        """Infer company name from title segments or nearby visible lines."""
        parts = _title_parts(page_title)
        if len(parts) >= 2 and parts[1].casefold() not in {"linkedin", "indeed", "glassdoor"}:
            return parts[1]
        lines = visible_text.splitlines()
        if raw_title in lines:
            index = lines.index(raw_title)
            if index + 1 < len(lines):
                return lines[index + 1]
        return lines[1] if len(lines) >= 2 else None

    @staticmethod
    def infer_location(
        visible_text: str,
        raw_title: str | None,
        company_name: str | None,
    ) -> str | None:
        """Infer a concise location from lines near the title and company."""
        lines = visible_text.splitlines()
        start = 0
        for value in (raw_title, company_name):
            if value in lines:
                start = max(start, lines.index(value) + 1)
        for line in lines[start : start + 4]:
            if len(line) <= 120 and not line.endswith((".", "!", "?")):
                return line
        return None

    @staticmethod
    def infer_employment_type(visible_text: str) -> str | None:
        """Infer a common employment type from visible text."""
        normalized = visible_text.casefold()
        for label, value in (
            ("full-time", "full_time"),
            ("full time", "full_time"),
            ("part-time", "part_time"),
            ("part time", "part_time"),
            ("contract", "contract"),
            ("internship", "internship"),
            ("freelance", "freelance"),
        ):
            if label in normalized:
                return value
        return None

    @staticmethod
    def infer_workplace_type(visible_text: str) -> str | None:
        """Infer remote, hybrid, or onsite arrangement from visible text."""
        normalized = visible_text.casefold()
        for label, value in (
            ("hybrid", "hybrid"),
            ("remote", "remote"),
            ("on-site", "onsite"),
            ("onsite", "onsite"),
        ):
            if label in normalized:
                return value
        return None

    @staticmethod
    def failure_result(
        job_url: str,
        platform: SourcePlatform,
        *warnings: str,
    ) -> JobUrlExtractionResult:
        """Build a safe non-pipeline-ready result."""
        return JobUrlExtractionResult(
            job_url=job_url,
            detected_platform=platform,
            description_text="",
            extraction_confidence=Decimal("0"),
            extraction_warnings=list(warnings),
            pipeline_ready=False,
        )

    @staticmethod
    def _selector_fields(
        page: Page,
        platform: SourcePlatform,
        job_url: str,
    ) -> dict[str, str | None]:
        """Read the first visible text value from platform-specific selectors."""
        domain = (urlparse(job_url).hostname or "").casefold()
        selector_map = PLATFORM_SELECTORS.get(platform, {})
        for domain_suffix, domain_selectors in DOMAIN_SELECTORS.items():
            if domain == domain_suffix or domain.endswith(f".{domain_suffix}"):
                selector_map = domain_selectors
                break
        fields: dict[str, str | None] = {}
        for field, selectors in selector_map.items():
            fields[field] = _first_visible_selector_text(page, selectors)
        return fields

    @staticmethod
    def _confidence(
        *,
        title: str | None,
        company: str | None,
        location: str | None,
        description: str,
        selector_fields: dict[str, str | None],
    ) -> Decimal:
        """Calculate a bounded, explainable extraction confidence."""
        score = Decimal("0")
        score += Decimal("0.25") if title else Decimal("0")
        score += Decimal("0.25") if company else Decimal("0")
        score += Decimal("0.10") if location else Decimal("0")
        score += Decimal("0.30") if len(description) >= 80 else Decimal("0")
        score += Decimal("0.10") if any(selector_fields.values()) else Decimal("0")
        return min(Decimal("1"), score)


def _first_visible_selector_text(page: Page, selectors: tuple[str, ...]) -> str | None:
    """Return text from the first matching visible selector."""
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            if locator.is_visible():
                value = locator.inner_text().strip()
                if value:
                    return value
        except PlaywrightTimeoutError:
            continue
    return None


def _title_parts(page_title: str) -> list[str]:
    """Split a page title into useful title segments."""
    return [
        part.strip()
        for part in re.split(r"\s+(?:[-|]|at)\s+", page_title)
        if part.strip() and not part.strip().casefold().startswith("job search")
    ]


def _title_part(page_title: str) -> str | None:
    """Return the likely job-title segment from a page title."""
    parts = _title_parts(page_title)
    return parts[0] if parts else None


def _first_line(visible_text: str) -> str | None:
    """Return the first concise visible line."""
    for line in visible_text.splitlines():
        if 1 <= len(line) <= 250:
            return line
    return None
