"""Registry of available connectors. New integrations register here (ARCH-009)."""
from __future__ import annotations

from typing import Callable

from .aws_sim import AwsSimConnector
from .base import Connector
from .openproject import OpenProjectConnector

_REGISTRY: dict[str, Callable[[], Connector]] = {
    "openproject": OpenProjectConnector,
    "aws": AwsSimConnector,
    # Phase 2+: jira, zoho_crm, greythr, hubspot, ga4, diib, readai, finance ...
}


def get_connector(source: str) -> Connector | None:
    factory = _REGISTRY.get(source)
    return factory() if factory else None


def sources() -> list[str]:
    return list(_REGISTRY)
