"""Small OpenAI SDK wrapper used by optional AI features."""

from __future__ import annotations

import json
from typing import Any


class OpenAIResumeClient:
    """Create structured JSON responses without leaking application secrets."""

    def __init__(self, *, api_key: str, model: str) -> None:
        """Store credentials for lazy SDK initialization."""
        self.api_key = api_key
        self.model = model

    def create_json_response(
        self,
        *,
        system_prompt: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Call OpenAI chat completions and return a JSON object."""
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - depends on optional install state
            raise RuntimeError("The openai package is not installed.") from exc

        client = OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        "Return JSON with keys: professional_summary, skill_groups, "
                        "selected_projects, excluded_projects, resume_strategy_notes, "
                        "truthfulness_warnings, cloud_certification_notes.\n\n"
                        f"{json.dumps(payload, default=str)}"
                    ),
                },
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("OpenAI returned an empty resume-quality response.")
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise RuntimeError("OpenAI resume-quality response was not a JSON object.")
        return parsed
