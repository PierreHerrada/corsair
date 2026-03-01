from __future__ import annotations

import logging
from typing import ClassVar, Optional

from app.integrations.base import BaseIntegration
from app.integrations.github.client import GitHubIntegration
from app.integrations.jira.client import JiraIntegration
from app.integrations.slack.bot import SlackIntegration

logger = logging.getLogger(__name__)

# Default integrations to register on first initialize
_DEFAULT_INTEGRATIONS: list[type[BaseIntegration]] = [
    SlackIntegration,
    JiraIntegration,
    GitHubIntegration,
]


class IntegrationRegistry:
    _integrations: ClassVar[list[BaseIntegration]] = []
    _active: ClassVar[list[BaseIntegration]] = []

    @classmethod
    def register(cls, integration_class: type[BaseIntegration]) -> None:
        instance = integration_class()
        cls._integrations.append(instance)

    @classmethod
    def initialize(cls) -> None:
        # Register defaults if registry is empty
        if not cls._integrations:
            for integration_class in _DEFAULT_INTEGRATIONS:
                cls.register(integration_class)
        cls._active = []
        for integration in cls._integrations:
            missing = integration.check_env_vars()
            if missing:
                logger.info(
                    "Integration '%s' inactive — missing env vars: %s",
                    integration.name,
                    ", ".join(missing),
                )
            else:
                cls._active.append(integration)
                logger.info("Integration '%s' active", integration.name)

    @classmethod
    def get_all(cls) -> list[BaseIntegration]:
        return cls._integrations

    @classmethod
    def get_active(cls) -> list[BaseIntegration]:
        return cls._active

    @classmethod
    def get(cls, name: str) -> Optional[BaseIntegration]:
        for integration in cls._active:
            if integration.name == name:
                return integration
        return None

    @classmethod
    def get_status(cls) -> list[dict]:
        result = []
        for integration in cls._integrations:
            missing = integration.check_env_vars()
            result.append(
                {
                    "name": integration.name,
                    "description": integration.description,
                    "active": len(missing) == 0,
                    "missing_env_vars": missing,
                }
            )
        return result

    @classmethod
    def reset(cls) -> None:
        """Reset registry — used in tests."""
        cls._integrations = []
        cls._active = []
