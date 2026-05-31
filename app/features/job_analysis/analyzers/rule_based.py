"""Deterministic local job-description extraction for Job Analyzer Engine v1."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

from app.features.job_analysis.analyzers.base import BaseJobAnalyzer
from app.models.enums import SeniorityLevel, WorkplaceType
from app.schemas import JobAnalysisResult, JobDescriptionInput

PREFERRED_MARKERS = (
    "bonus",
    "desired",
    "ideally",
    "nice to have",
    "nice-to-have",
    "preferred",
    "plus",
)

TECHNOLOGIES: dict[str, tuple[str, ...]] = {
    "Python": ("python",),
    "JavaScript": ("javascript",),
    "TypeScript": ("typescript",),
    "Java": ("java",),
    "C++": ("c++",),
    "C#": ("c#",),
    "Go": ("golang", "go language"),
    "Rust": ("rust",),
    "SQL": ("sql",),
    "PostgreSQL": ("postgresql", "postgres"),
    "MySQL": ("mysql",),
    "MongoDB": ("mongodb", "mongo"),
    "Redis": ("redis",),
    "AWS": ("aws", "amazon web services"),
    "Azure": ("azure",),
    "GCP": ("gcp", "google cloud"),
    "Docker": ("docker",),
    "Kubernetes": ("kubernetes", "k8s"),
    "Terraform": ("terraform",),
    "Git": ("git",),
    "Linux": ("linux",),
    "FastAPI": ("fastapi",),
    "Django": ("django",),
    "Flask": ("flask",),
    "React": ("react", "react.js"),
    "Node.js": ("node.js", "nodejs"),
    "PyTorch": ("pytorch",),
    "TensorFlow": ("tensorflow",),
    "scikit-learn": ("scikit-learn", "sklearn"),
    "LangChain": ("langchain",),
    "LangGraph": ("langgraph",),
    "OpenAI": ("openai",),
    "APIs": ("api", "rest api", "restful api"),
    "Webhooks": ("webhook",),
    "GraphQL": ("graphql",),
    "Kafka": ("kafka",),
    "Spark": ("apache spark", "spark"),
    "Airflow": ("airflow",),
    "Snowflake": ("snowflake",),
    "Embeddings": ("embedding",),
    "Selenium": ("selenium",),
    "Playwright": ("playwright",),
    "BeautifulSoup": ("beautifulsoup", "beautiful soup"),
    "GitHub": ("github",),
    "n8n": ("n8n",),
    "Zapier": ("zapier",),
    "Make": ("make.com",),
    "Slack": ("slack",),
    "Amazon Seller Central": ("amazon seller central",),
}

SKILLS: dict[str, tuple[str, ...]] = {
    "Artificial Intelligence": ("artificial intelligence",),
    "Machine Learning": ("machine learning",),
    "Generative AI": ("generative ai", "genai"),
    "Natural Language Processing": ("natural language processing", "nlp"),
    "Large Language Models": ("large language model", "llm"),
    "Retrieval-Augmented Generation": ("retrieval-augmented generation", "rag"),
    "Prompt Engineering": ("prompt engineering",),
    "Vector Databases": ("vector database", "vector store"),
    "Data Engineering": ("data engineering",),
    "Backend Development": ("backend development", "backend engineer"),
    "API Design": ("api design",),
    "Microservices": ("microservice",),
    "Distributed Systems": ("distributed system",),
    "Cloud Computing": ("cloud computing", "cloud architecture"),
    "DevOps": ("devops",),
    "CI/CD": ("ci/cd", "continuous integration"),
    "Test Automation": ("test automation", "automated testing"),
    "System Design": ("system design",),
    "Data Structures": ("data structure",),
    "Algorithms": ("algorithm",),
    "Automation": ("automation", "automated workflow"),
    "Web Scraping": ("web scraping", "scraping"),
    "AI Agents": ("ai agent", "agent workflow", "agents"),
    "Workflow Design": ("workflow",),
}

SOFT_SKILLS: dict[str, tuple[str, ...]] = {
    "Communication": ("communication", "communicate"),
    "Collaboration": ("collaboration", "collaborate", "cross-functional"),
    "Leadership": ("leadership", "mentor", "mentoring"),
    "Problem Solving": ("problem solving", "problem-solving"),
    "Ownership": ("ownership", "self-starter"),
    "Adaptability": ("adaptability", "adaptable"),
}

DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "SaaS": ("saas",),
    "FinTech": ("fintech", "financial technology"),
    "HealthTech": ("healthtech", "healthcare"),
    "E-commerce": ("e-commerce", "ecommerce"),
    "Cybersecurity": ("cybersecurity", "information security"),
    "Developer Tools": ("developer tools", "developer platform"),
    "Data Platform": ("data platform",),
    "AI Platform": ("ai platform",),
}

RED_FLAG_RULES: dict[str, str] = {
    "rockstar": "Uses vague 'rockstar' language",
    "ninja": "Uses vague 'ninja' language",
    "unpaid": "Mentions unpaid work",
    "wear many hats": "Suggests an unusually broad role scope",
    "always on": "May imply an always-on availability expectation",
    "24/7": "May imply a 24/7 availability expectation",
    "equity only": "Mentions equity-only compensation",
    "competitive compensation": "Uses vague compensation wording",
    "competitive salary": "Uses vague compensation wording",
    "unpaid test": "Mentions an unpaid test task",
    "unpaid assignment": "Mentions an unpaid test task",
    "too good to be true": "Uses suspicious wording",
}

SECTION_HEADINGS = {
    "responsibilities": "responsibilities",
    "what you will do": "responsibilities",
    "what you'll do": "responsibilities",
    "the role": "responsibilities",
    "requirements": "qualifications",
    "qualifications": "qualifications",
    "what we are looking for": "qualifications",
    "what we're looking for": "qualifications",
    "preferred qualifications": "preferred",
    "preferred skills": "preferred",
    "nice to have": "preferred",
    "nice-to-have": "preferred",
}

RESPONSIBILITY_VERBS = (
    "architect",
    "build",
    "collaborate",
    "create",
    "deliver",
    "design",
    "develop",
    "drive",
    "implement",
    "lead",
    "maintain",
    "manage",
    "optimize",
    "own",
    "partner",
    "support",
)


class RuleBasedJobAnalyzer(BaseJobAnalyzer):
    """Extract repeatable job intelligence locally without external API calls."""

    @property
    def analyzer_name(self) -> str:
        """Return the provider identifier."""
        return "rule_based"

    @property
    def analyzer_version(self) -> str:
        """Return the extraction ruleset version."""
        return "1.0.0"

    def analyze(self, job_description: JobDescriptionInput) -> JobAnalysisResult:
        """Convert raw job text into deterministic structured intelligence."""
        job = job_description
        text = job.description_text.strip()
        contexts = self._contexts(text)
        sections = self._sections(text)
        normalized_title = self._normalize_title(job.raw_title)
        experience_min, experience_max = self._estimated_experience(text)
        seniority = self._seniority(normalized_title, text, experience_min)
        required_skills, preferred_skills = self._classified_keywords(contexts, SKILLS)
        required_technologies, preferred_technologies = self._classified_keywords(
            contexts, TECHNOLOGIES
        )
        soft_skills = self._keywords(text, SOFT_SKILLS)
        domain_keywords = self._keywords(text, DOMAIN_KEYWORDS)
        responsibilities = self._responsibilities(sections, contexts)
        qualifications = self._qualifications(sections)
        inferred_workplace = job.workplace_type or self._workplace_type(text)
        red_flags = self._red_flags(text, normalized_title)
        missing_information = self._missing_information(
            job=job,
            text=text,
            responsibilities=responsibilities,
            qualifications=qualifications,
            required_skills=required_skills,
            required_technologies=required_technologies,
            experience_min=experience_min,
            inferred_workplace=inferred_workplace,
        )
        ats_keywords = self._deduplicate(
            [
                normalized_title,
                *required_skills,
                *preferred_skills,
                *required_technologies,
                *preferred_technologies,
                *soft_skills,
                *domain_keywords,
            ]
        )
        signals = {
            "normalized_title": normalized_title,
            "seniority_level": seniority.value,
            "estimated_years_min": experience_min,
            "estimated_years_max": experience_max,
            "required_skills": required_skills,
            "preferred_skills": preferred_skills,
            "required_technologies": required_technologies,
            "preferred_technologies": preferred_technologies,
            "domain_keywords": domain_keywords,
            "location": job.location,
            "workplace_type": str(inferred_workplace) if inferred_workplace else None,
            "employment_type": job.employment_type,
            "salary": {
                "minimum": str(job.salary_min) if job.salary_min is not None else None,
                "maximum": str(job.salary_max) if job.salary_max is not None else None,
                "currency": job.currency,
            },
            "scoring_ready": True,
        }
        return JobAnalysisResult(
            normalized_title=normalized_title,
            seniority_level=seniority.value,
            estimated_years_min=experience_min,
            estimated_years_max=experience_max,
            required_skills=required_skills,
            preferred_skills=preferred_skills,
            required_technologies=required_technologies,
            preferred_technologies=preferred_technologies,
            responsibilities=responsibilities,
            qualifications=qualifications,
            soft_skills=soft_skills,
            domain_keywords=domain_keywords,
            ats_keywords=ats_keywords,
            red_flags=red_flags,
            missing_information=missing_information,
            job_summary=self._summary(
                job,
                normalized_title,
                seniority,
                required_skills,
                required_technologies,
            ),
            match_relevant_signals=signals,
        )

    @staticmethod
    def _normalize_title(raw_title: str) -> str:
        """Normalize common title abbreviations and remove workplace suffixes."""
        title = re.sub(r"\s*[\(\[]\s*(remote|hybrid|on-?site)\s*[\)\]]", "", raw_title, flags=re.I)
        title = re.sub(r"\bsr\.?(?=\s|$)", "Senior", title, flags=re.I)
        title = re.sub(r"\bjr\.?(?=\s|$)", "Junior", title, flags=re.I)
        title = re.sub(r"\bsw(e|d)\b", "Software Engineer", title, flags=re.I)
        return " ".join(title.split()).strip(" -|,")

    @classmethod
    def _classified_keywords(
        cls,
        contexts: list[str],
        catalog: Mapping[str, tuple[str, ...]],
    ) -> tuple[list[str], list[str]]:
        """Split extracted keywords into required and preferred groups."""
        required: list[str] = []
        preferred: list[str] = []
        for canonical, variants in catalog.items():
            matches = [
                context
                for context in contexts
                if any(cls._contains(context, variant) for variant in variants)
            ]
            if not matches:
                continue
            if all(cls._is_preferred(context) for context in matches):
                preferred.append(canonical)
            else:
                required.append(canonical)
        return required, preferred

    @classmethod
    def _keywords(
        cls,
        text: str,
        catalog: Mapping[str, tuple[str, ...]],
    ) -> list[str]:
        """Return canonical keyword names present in text."""
        return [
            canonical
            for canonical, variants in catalog.items()
            if any(cls._contains(text, variant) for variant in variants)
        ]

    @staticmethod
    def _contains(text: str, keyword: str) -> bool:
        """Match keywords without accidental word fragments."""
        pattern = rf"(?<![\w]){re.escape(keyword)}(?![\w])"
        return re.search(pattern, text, flags=re.I) is not None

    @staticmethod
    def _is_preferred(context: str) -> bool:
        """Return whether a sentence describes a preferred qualification."""
        lowered = context.lower()
        return any(marker in lowered for marker in PREFERRED_MARKERS)

    @staticmethod
    def _contexts(text: str) -> list[str]:
        """Split text into stable sentence and bullet contexts."""
        contexts: list[str] = []
        for line in text.splitlines():
            cleaned = RuleBasedJobAnalyzer._clean_line(line)
            if not cleaned:
                continue
            contexts.extend(part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part)
        return contexts or ([text] if text else [])

    @staticmethod
    def _sections(text: str) -> dict[str, list[str]]:
        """Collect bullet-like content under recognizable headings."""
        sections: dict[str, list[str]] = {
            "responsibilities": [],
            "qualifications": [],
            "preferred": [],
        }
        active_section: str | None = None
        for raw_line in text.splitlines():
            cleaned = RuleBasedJobAnalyzer._clean_line(raw_line)
            if not cleaned:
                continue
            heading = cleaned.lower().rstrip(":")
            if heading in SECTION_HEADINGS:
                active_section = SECTION_HEADINGS[heading]
                continue
            if active_section:
                sections[active_section].append(cleaned)
        return sections

    @staticmethod
    def _clean_line(line: str) -> str:
        """Remove common list prefixes and surrounding whitespace."""
        return re.sub(r"^\s*(?:[-*]|\u2022|\d+[.)])\s*", "", line).strip()

    @classmethod
    def _responsibilities(
        cls,
        sections: Mapping[str, list[str]],
        contexts: list[str],
    ) -> list[str]:
        """Extract responsibilities from sections or action-oriented statements."""
        if sections["responsibilities"]:
            return cls._deduplicate(sections["responsibilities"])
        detected = []
        for context in contexts:
            first_word = context.lower().split(maxsplit=1)[0].rstrip(":") if context else ""
            if first_word in RESPONSIBILITY_VERBS:
                detected.append(context)
        return cls._deduplicate(detected)

    @classmethod
    def _qualifications(cls, sections: Mapping[str, list[str]]) -> list[str]:
        """Extract qualification and preference statements."""
        return cls._deduplicate([*sections["qualifications"], *sections["preferred"]])

    @staticmethod
    def _estimated_experience(text: str) -> tuple[int | None, int | None]:
        """Extract numeric years-of-experience bounds from the first requirement."""
        match = re.search(
            r"\b(\d{1,2})\s*(?:-\s*(\d{1,2})|\+)?\s*(?:years?|yrs?)(?:\s+of)?\s+experience\b",
            text,
            flags=re.I,
        )
        if not match:
            return None, None
        lower, upper = match.groups()
        if upper:
            return int(lower), int(upper)
        if "+" in match.group(0):
            return int(lower), None
        return int(lower), int(lower)

    @staticmethod
    def _seniority(
        normalized_title: str,
        text: str,
        experience_min: int | None,
    ) -> SeniorityLevel:
        """Infer normalized seniority from title, text, and experience."""
        title = normalized_title.lower()
        ordered_title_rules = (
            ("intern", SeniorityLevel.INTERN),
            ("junior", SeniorityLevel.JUNIOR),
            ("entry", SeniorityLevel.JUNIOR),
            ("principal", SeniorityLevel.PRINCIPAL),
            ("staff", SeniorityLevel.STAFF),
            ("lead", SeniorityLevel.LEAD),
            ("manager", SeniorityLevel.MANAGER),
            ("director", SeniorityLevel.DIRECTOR),
            ("chief", SeniorityLevel.EXECUTIVE),
            ("vp", SeniorityLevel.EXECUTIVE),
            ("senior", SeniorityLevel.SENIOR),
        )
        for marker, seniority in ordered_title_rules:
            if marker in title:
                return seniority
        if experience_min is not None:
            if experience_min >= 8:
                return SeniorityLevel.SENIOR
            if experience_min >= 3:
                return SeniorityLevel.MID_LEVEL
            return SeniorityLevel.JUNIOR
        if re.search(r"\bmid[- ]level\b", text, flags=re.I):
            return SeniorityLevel.MID_LEVEL
        return SeniorityLevel.UNKNOWN

    @staticmethod
    def _workplace_type(text: str) -> WorkplaceType | None:
        """Infer workplace arrangement if the source did not supply one."""
        lowered = text.lower()
        if "hybrid" in lowered:
            return WorkplaceType.HYBRID
        if "remote" in lowered:
            return WorkplaceType.REMOTE
        if "on-site" in lowered or "onsite" in lowered or "in office" in lowered:
            return WorkplaceType.ONSITE
        return None

    @staticmethod
    def _red_flags(text: str, normalized_title: str) -> list[str]:
        """Flag explicit phrases that deserve candidate review."""
        lowered = text.lower()
        red_flags = [message for phrase, message in RED_FLAG_RULES.items() if phrase in lowered]
        experience_min, _ = RuleBasedJobAnalyzer._estimated_experience(text)
        junior_title = re.search(r"\b(?:intern|junior|entry[- ]level)\b", normalized_title, re.I)
        if junior_title and experience_min is not None and experience_min >= 5:
            red_flags.append("Contains unrealistic requirements for the advertised seniority")
        return RuleBasedJobAnalyzer._deduplicate(red_flags)

    @staticmethod
    def _missing_information(
        *,
        job: JobDescriptionInput,
        text: str,
        responsibilities: list[str],
        qualifications: list[str],
        required_skills: list[str],
        required_technologies: list[str],
        experience_min: int | None,
        inferred_workplace: WorkplaceType | str | None,
    ) -> list[str]:
        """Identify absent fields and weak extraction signals."""
        missing = []
        if len(text) < 80:
            missing.append("detailed job description")
        if not job.company_name:
            missing.append("company name")
        if not job.location:
            missing.append("location")
        if job.salary_min is None and job.salary_max is None:
            missing.append("salary range")
        if not job.employment_type:
            missing.append("employment type")
        if inferred_workplace is None:
            missing.append("workplace type")
        if not responsibilities:
            missing.append("responsibilities")
        if not qualifications:
            missing.append("qualifications")
        if not required_skills and not required_technologies:
            missing.append("required skills or technologies")
        if experience_min is None:
            missing.append("experience requirement")
        return missing

    @staticmethod
    def _summary(
        job: JobDescriptionInput,
        normalized_title: str,
        seniority: SeniorityLevel,
        required_skills: list[str],
        required_technologies: list[str],
    ) -> str:
        """Build a compact deterministic summary for downstream consumers."""
        keywords = [*required_skills, *required_technologies][:6]
        summary = f"{normalized_title} role at {job.company_name or 'an unspecified company'}"
        if seniority is not SeniorityLevel.UNKNOWN:
            summary += f" with {seniority.value}-level scope"
        if keywords:
            summary += f". Core requirements include {', '.join(keywords)}"
        return f"{summary}."

    @staticmethod
    def _deduplicate(values: Iterable[str]) -> list[str]:
        """Deduplicate values while preserving source order."""
        return list(dict.fromkeys(value for value in values if value))
