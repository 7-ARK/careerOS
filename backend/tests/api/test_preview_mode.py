"""Focused safety checks for the externally tunneled deterministic preview."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.api.routes.applications import _reject_external_preview_application_mutation
from app.api.routes.auth import _reject_external_preview_registration
from app.api.routes.candidates import _reject_external_preview_candidate_mutation
from app.api.routes.career_analysis import _reject_external_preview_live_mode
from app.api.routes.job_url_extraction import _reject_external_preview_extraction
from app.api.routes.pipeline import _reject_external_preview_auto_export


def test_preview_mode_blocks_live_and_external_action_paths() -> None:
    with patch.dict("os.environ", {"CAREEROS_PREVIEW_MODE": "true"}, clear=True):
        with pytest.raises(HTTPException) as live_error:
            _reject_external_preview_live_mode("live")
        with pytest.raises(HTTPException) as extraction_error:
            _reject_external_preview_extraction()
        with pytest.raises(HTTPException) as legacy_error:
            _reject_external_preview_auto_export()
        with pytest.raises(HTTPException) as registration_error:
            _reject_external_preview_registration()
        with pytest.raises(HTTPException) as candidate_error:
            _reject_external_preview_candidate_mutation()
        with pytest.raises(HTTPException) as application_error:
            _reject_external_preview_application_mutation()

    assert live_error.value.status_code == 403
    assert extraction_error.value.status_code == 403
    assert legacy_error.value.status_code == 403
    assert registration_error.value.status_code == 403
    assert candidate_error.value.status_code == 403
    assert application_error.value.status_code == 403


def test_preview_mode_keeps_mock_golden_flow_available() -> None:
    with patch.dict("os.environ", {"CAREEROS_PREVIEW_MODE": "true"}, clear=True):
        _reject_external_preview_live_mode("mock")
