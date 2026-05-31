"""Health endpoint and framework-independent status helper."""

from dataclasses import asdict, dataclass

from fastapi import APIRouter

from app import __version__

APP_NAME = "careerOS"
APP_VERSION = __version__

router = APIRouter(tags=["health"])


@dataclass(frozen=True, slots=True)
class HealthStatus:
    """Serializable application health status."""

    name: str
    version: str
    status: str


def get_health_status() -> dict[str, str]:
    """Return the framework-independent health payload."""
    return asdict(HealthStatus(name=APP_NAME, version=APP_VERSION, status="ok"))


@router.get("/health")
def health() -> dict[str, str]:
    """Return API health metadata."""
    status = get_health_status()
    return {
        "status": status["status"],
        "service": status["name"],
        "version": status["version"],
    }
