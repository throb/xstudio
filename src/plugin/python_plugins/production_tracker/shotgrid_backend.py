# SPDX-License-Identifier: Apache-2.0

"""ShotGrid (Flow Production Tracking) backend implementation.

Uses the ``shotgun_api3`` package when available.  If the package is
missing the module still imports successfully but ``authenticate()``
will always return False with a descriptive error message.
"""

from __future__ import annotations

import json
import os
import traceback
from typing import Any

from .tracker_backend import TrackerBackend

# ---------------------------------------------------------------------------
# Optional dependency -- load from vendored directory first, then system
# ---------------------------------------------------------------------------
_VENDOR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")

try:
    import sys

    if _VENDOR_DIR not in sys.path:
        sys.path.insert(0, _VENDOR_DIR)
    import shotgun_api3  # type: ignore[import-untyped]

    _SHOTGUN_AVAILABLE = True
except ImportError:
    _SHOTGUN_AVAILABLE = False
    shotgun_api3 = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Default field lists (overridable via config.json)
# ---------------------------------------------------------------------------
_DEFAULT_VERSION_FIELDS = [
    "id",
    "code",
    "description",
    "created_at",
    "user",
    "sg_status_list",
    "sg_path_to_frames",
    "sg_path_to_movie",
    "frame_count",
    "frame_range",
    "image",
    "entity",
    "project",
]

_DEFAULT_PROJECT_FIELDS = ["id", "name", "sg_status"]
_DEFAULT_SEQUENCE_FIELDS = ["id", "code", "sg_status"]
_DEFAULT_SHOT_FIELDS = [
    "id",
    "code",
    "sg_status",
    "sg_sequence",
    "sg_cut_in",
    "sg_cut_out",
]

_PAGE_SIZE = 100
_ACTIVE_PROJECT_STATUSES = ["Active"]


def _load_field_config() -> dict:
    """Load field configuration from ``config.json`` next to the package."""
    config_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "config.json"
    )
    try:
        with open(config_path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


class ShotGridBackend(TrackerBackend):
    """ShotGrid / Flow Production Tracking backend."""

    def __init__(self) -> None:
        self._sg: Any | None = None
        self._connected: bool = False
        self._config: dict = _load_field_config()
        sg_cfg = self._config.get("shotgrid", {})
        self._version_fields: list[str] = sg_cfg.get(
            "default_version_fields", _DEFAULT_VERSION_FIELDS
        )
        self._project_fields: list[str] = sg_cfg.get(
            "project_fields", _DEFAULT_PROJECT_FIELDS
        )
        self._sequence_fields: list[str] = sg_cfg.get(
            "sequence_fields", _DEFAULT_SEQUENCE_FIELDS
        )
        self._shot_fields: list[str] = sg_cfg.get(
            "shot_fields", _DEFAULT_SHOT_FIELDS
        )
        self._page_size: int = sg_cfg.get("page_size", _PAGE_SIZE)
        self._active_statuses: list[str] = sg_cfg.get(
            "active_project_statuses", _ACTIVE_PROJECT_STATUSES
        )

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self, **credentials: Any) -> tuple[bool, str]:
        """Returns (success, error_message)."""
        if not _SHOTGUN_AVAILABLE:
            return False, (
                "shotgun_api3 is not installed. "
                "Install it with:  pip install shotgun_api3"
            )

        site_url: str = credentials.get("site_url", "").rstrip("/")
        script_name: str = credentials.get("script_name", "")
        api_key: str = credentials.get("api_key", "")
        login: str = credentials.get("login", "")
        password: str = credentials.get("password", "")

        if not site_url:
            return False, "Site URL is required"

        try:
            if script_name and api_key:
                self._sg = shotgun_api3.Shotgun(
                    site_url,
                    script_name=script_name,
                    api_key=api_key,
                )
            elif login and password:
                self._sg = shotgun_api3.Shotgun(
                    site_url,
                    login=login,
                    password=password,
                )
            else:
                return False, "Provide either (Script Name + API Key) or (Login + Password)"

            # Validate the connection with a lightweight query
            self._sg.find_one("Project", [], ["id"])
            self._connected = True
            return True, ""

        except Exception as exc:
            traceback.print_exc()
            self._sg = None
            self._connected = False
            return False, str(exc)

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def get_projects(self) -> list[dict]:
        if not self._ensure_connected():
            return []
        try:
            filters = [["sg_status", "in", self._active_statuses]]
            raw = self._sg.find(
                "Project",
                filters,
                self._project_fields,
                order=[{"field_name": "name", "direction": "asc"}],
            )
            return [self._sanitize(p) for p in raw]
        except Exception as exc:
            print(f"ProductionTracker: get_projects failed -- {exc}")
            traceback.print_exc()
            return []

    # ------------------------------------------------------------------
    # Sequences
    # ------------------------------------------------------------------

    def get_sequences(self, project_id: int) -> list[dict]:
        if not self._ensure_connected():
            return []
        try:
            filters = [["project", "is", {"type": "Project", "id": project_id}]]
            raw = self._sg.find(
                "Sequence",
                filters,
                self._sequence_fields,
                order=[{"field_name": "code", "direction": "asc"}],
            )
            return [self._sanitize(s) for s in raw]
        except Exception as exc:
            print(f"ProductionTracker: get_sequences failed -- {exc}")
            traceback.print_exc()
            return []

    # ------------------------------------------------------------------
    # Shots
    # ------------------------------------------------------------------

    def get_shots(
        self, project_id: int, sequence_id: int | None = None
    ) -> list[dict]:
        if not self._ensure_connected():
            return []
        try:
            filters: list = [
                ["project", "is", {"type": "Project", "id": project_id}]
            ]
            if sequence_id is not None:
                filters.append(
                    [
                        "sg_sequence",
                        "is",
                        {"type": "Sequence", "id": sequence_id},
                    ]
                )
            raw = self._sg.find(
                "Shot",
                filters,
                self._shot_fields,
                order=[{"field_name": "code", "direction": "asc"}],
            )
            return [self._sanitize(s) for s in raw]
        except Exception as exc:
            print(f"ProductionTracker: get_shots failed -- {exc}")
            traceback.print_exc()
            return []

    # ------------------------------------------------------------------
    # Versions
    # ------------------------------------------------------------------

    def get_versions(
        self,
        entity_type: str,
        entity_id: int,
        fields: list[str] | None = None,
    ) -> list[dict]:
        if not self._ensure_connected():
            return []
        try:
            filters = [
                ["entity", "is", {"type": entity_type, "id": entity_id}]
            ]
            use_fields = fields if fields else self._version_fields
            raw = self._sg.find(
                "Version",
                filters,
                use_fields,
                order=[{"field_name": "created_at", "direction": "desc"}],
                limit=self._page_size,
            )
            return [self._sanitize(v) for v in raw]
        except Exception as exc:
            print(f"ProductionTracker: get_versions failed -- {exc}")
            traceback.print_exc()
            return []

    def get_version_detail(self, version_id: int) -> dict:
        if not self._ensure_connected():
            return {}
        try:
            raw = self._sg.find_one(
                "Version",
                [["id", "is", version_id]],
                self._version_fields,
            )
            return self._sanitize(raw) if raw else {}
        except Exception as exc:
            print(f"ProductionTracker: get_version_detail failed -- {exc}")
            traceback.print_exc()
            return {}

    def search_versions(self, project_id: int, text: str) -> list[dict]:
        if not self._ensure_connected():
            return []
        try:
            filters = [
                ["project", "is", {"type": "Project", "id": project_id}],
                ["code", "contains", text],
            ]
            raw = self._sg.find(
                "Version",
                filters,
                self._version_fields,
                order=[{"field_name": "created_at", "direction": "desc"}],
                limit=self._page_size,
            )
            return [self._sanitize(v) for v in raw]
        except Exception as exc:
            print(f"ProductionTracker: search_versions failed -- {exc}")
            traceback.print_exc()
            return []

    # ------------------------------------------------------------------
    # Thumbnails
    # ------------------------------------------------------------------

    def get_thumbnail_url(self, entity_type: str, entity_id: int) -> str:
        if not self._ensure_connected():
            return ""
        try:
            result = self._sg.find_one(
                entity_type, [["id", "is", entity_id]], ["image"]
            )
            return result.get("image", "") if result else ""
        except Exception as exc:
            print(f"ProductionTracker: get_thumbnail_url failed -- {exc}")
            return ""

    def get_movie_url(self, version_id: int) -> str:
        """Return URL for the uploaded movie on ShotGrid, or empty string."""
        if not self._ensure_connected():
            return ""
        try:
            result = self._sg.find_one(
                "Version",
                [["id", "is", version_id]],
                ["sg_uploaded_movie"],
            )
            if result and result.get("sg_uploaded_movie"):
                movie = result["sg_uploaded_movie"]
                if isinstance(movie, dict):
                    return movie.get("url", "")
            return ""
        except Exception as exc:
            print(f"ProductionTracker: get_movie_url failed -- {exc}")
            return ""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def disconnect(self) -> None:
        if self._sg is not None:
            try:
                self._sg.close()
            except Exception:
                pass
        self._sg = None
        self._connected = False
        print("ProductionTracker: disconnected from ShotGrid")

    @property
    def is_connected(self) -> bool:
        return self._connected and self._sg is not None

    @property
    def backend_name(self) -> str:
        return "ShotGrid"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ensure_connected(self) -> bool:
        if not self.is_connected:
            print("ProductionTracker: not connected")
            return False
        return True

    @staticmethod
    def _sanitize(record: dict | None) -> dict:
        """Make a ShotGrid record JSON-serializable.

        ShotGrid returns ``datetime`` objects and nested entity dicts
        that ``json.dumps`` cannot handle out of the box.  This converts
        everything to plain strings/dicts recursively.
        """
        if record is None:
            return {}
        out: dict = {}
        for key, value in record.items():
            if key == "type":
                # ShotGrid entity type field -- keep as-is
                out[key] = value
            elif hasattr(value, "isoformat"):
                # datetime / date
                out[key] = value.isoformat()
            elif isinstance(value, dict):
                # Nested entity reference -- flatten to id + name/code
                out[key] = {
                    "id": value.get("id"),
                    "name": value.get("name", value.get("code", "")),
                    "type": value.get("type", ""),
                }
            elif isinstance(value, (list, tuple)):
                out[key] = [
                    ShotGridBackend._sanitize(v)
                    if isinstance(v, dict)
                    else str(v) if hasattr(v, "isoformat") else v
                    for v in value
                ]
            else:
                out[key] = value
        return out
