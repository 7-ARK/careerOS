"""Schema tests for the end-to-end manual application pipeline."""

import unittest
from uuid import uuid4

from pydantic import ValidationError

from app.models.enums import DocumentFormat, ResumeTemplateName
from app.schemas import ManualJobPipelineRequest


class ManualJobPipelineSchemaTests(unittest.TestCase):
    """Verify pipeline defaults and inherited manual-import validation."""

    def test_defaults_to_clean_ats_pdf_and_application_record(self) -> None:
        request = self._request()

        self.assertEqual(request.resume_template_name, ResumeTemplateName.CLEAN_ATS)
        self.assertEqual(request.document_format, DocumentFormat.PDF)
        self.assertTrue(request.create_application_record)

    def test_rejects_invalid_required_text_format_and_template(self) -> None:
        for values in (
            {"description_text": " "},
            {"company_name": " "},
            {"raw_title": " "},
            {"document_format": "rtf"},
            {"resume_template_name": "decorative_columns"},
        ):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                self._request(**values)

    @staticmethod
    def _request(**overrides: object) -> ManualJobPipelineRequest:
        """Build a valid pipeline request with optional overrides."""
        values = {
            "candidate_profile_id": uuid4(),
            "raw_title": "Backend Engineer",
            "company_name": "Platform Labs",
            "source_platform": "LinkedIn",
            "description_text": "Build Python APIs.",
        }
        values.update(overrides)
        return ManualJobPipelineRequest(**values)


if __name__ == "__main__":
    unittest.main()
