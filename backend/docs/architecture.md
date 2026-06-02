# careerOS Architecture

careerOS is organized as a modular Python application with feature-oriented
domain packages and shared infrastructure layers.

## Layers

* `app/api/` exposes HTTP endpoints and dependency providers.
* `app/core/` owns shared configuration and foundational behavior.
* `app/db/`, `app/models/`, and `app/schemas/` prepare the persistence boundary.
* `app/ai/` contains provider clients, prompt templates, and LangGraph workflows.
* `app/features/` isolates career-domain capabilities.
* `app/integrations/` reserves external platform and browser automation adapters.

## Growth Path

The scaffold intentionally starts with no runtime dependencies. FastAPI,
PostgreSQL tooling, OpenAI clients, and LangGraph can be introduced as their
first concrete use cases are implemented.
