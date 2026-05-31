"""Framework-agnostic health reporting for the future API layer."""

from dataclasses import asdict, dataclass

from app.main import APP_NAME, APP_VERSION


@dataclass(frozen=True, slots=True)
class HealthStatus:
    """Serializable application health status."""

    name: str
    version: str
    status: str


def get_health_status() -> dict[str, str]:
    """Return a basic service health payload."""
    return asdict(HealthStatus(name=APP_NAME, version=APP_VERSION, status="ok"))
