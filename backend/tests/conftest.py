"""Pytest options for optional browser integration tests."""

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the explicit opt-in flag for local Playwright browser tests."""
    parser.addoption(
        "--run-browser",
        action="store_true",
        default=False,
        help="run optional Playwright browser integration tests",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip browser-marked tests unless the caller explicitly enables them."""
    if config.getoption("--run-browser"):
        return
    marker = pytest.mark.skip(reason="requires --run-browser and installed Playwright Chromium")
    for item in items:
        if "browser" in item.keywords:
            item.add_marker(marker)
