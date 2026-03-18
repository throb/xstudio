# SPDX-License-Identifier: Apache-2.0

from abc import ABC, abstractmethod
from typing import Any


class TrackerBackend(ABC):
    """Abstract production tracker interface.

    Provides a uniform API for querying production tracking systems
    (ShotGrid, Ftrack, Flow, etc.) from within xSTUDIO.  Concrete
    implementations must handle authentication, entity queries, and
    graceful error recovery.
    """

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    @abstractmethod
    def authenticate(self, **credentials: Any) -> tuple[bool, str]:
        """Authenticate with the tracker service.

        Keyword arguments are backend-specific (e.g. site_url,
        script_name, api_key for ShotGrid).

        Returns (True, "") on success, (False, error_message) on failure.
        """
        ...

    # ------------------------------------------------------------------
    # Entity queries
    # ------------------------------------------------------------------

    @abstractmethod
    def get_projects(self) -> list[dict]:
        """Return a list of active projects.

        Each dict contains at minimum: id, name, sg_status.
        """
        ...

    @abstractmethod
    def get_sequences(self, project_id: int) -> list[dict]:
        """Return sequences for the given project.

        Each dict contains at minimum: id, code, sg_status.
        """
        ...

    @abstractmethod
    def get_shots(
        self, project_id: int, sequence_id: int | None = None
    ) -> list[dict]:
        """Return shots for the given project, optionally filtered by sequence.

        Each dict contains at minimum: id, code, sg_status, sg_sequence.
        """
        ...

    @abstractmethod
    def get_versions(
        self,
        entity_type: str,
        entity_id: int,
        fields: list[str] | None = None,
    ) -> list[dict]:
        """Return versions linked to the specified entity.

        ``entity_type`` is typically ``"Shot"`` or ``"Asset"``.
        ``fields`` overrides the default field list when provided.
        """
        ...

    @abstractmethod
    def get_version_detail(self, version_id: int) -> dict:
        """Return full detail for a single version."""
        ...

    @abstractmethod
    def search_versions(self, project_id: int, text: str) -> list[dict]:
        """Free-text search for versions within a project."""
        ...

    @abstractmethod
    def get_thumbnail_url(self, entity_type: str, entity_id: int) -> str:
        """Return the thumbnail URL for an entity, or empty string."""
        ...

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    def disconnect(self) -> None:
        """Cleanly disconnect from the tracker service."""
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """True when an authenticated session is active."""
        ...

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Human-readable name of this backend (e.g. ``'ShotGrid'``)."""
        ...
