# SPDX-License-Identifier: Apache-2.0

"""Production Tracker plugin for xSTUDIO.

Provides a panel for browsing ShotGrid (or other production tracking
systems) directly within xSTUDIO, loading versions into playlists for
review.

Communication between Python and QML uses JSON-serialized xSTUDIO
attributes.  Commands flow QML -> Python via the ``command_channel``
attribute; data flows Python -> QML via dedicated data attributes.
"""

from __future__ import annotations

import json
import os
import threading
import traceback
from typing import Any

from xstudio.plugin import PluginBase
from xstudio.core import AttributeRole

from .tracker_backend import TrackerBackend


# ---------------------------------------------------------------------------
# Debug logging (file-based, same pattern as filesystem_browser)
# ---------------------------------------------------------------------------
import tempfile

_DEBUG_LOG = os.path.join(tempfile.gettempdir(), "xstudio_tracker_debug.txt")


def _dbg(msg: str) -> None:
    try:
        with open(_DEBUG_LOG, "a") as fh:
            fh.write(f"{msg}\n")
            fh.flush()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------

class ProductionTrackerPlugin(PluginBase):
    """xSTUDIO Python plugin for production tracking integration."""

    def __init__(self, connection: Any) -> None:
        PluginBase.__init__(
            self,
            connection,
            "Production Tracker",
            qml_folder="qml/ProductionTracker.1",
        )

        self.config = self._load_config()
        self.backend: TrackerBackend | None = None

        # ==================================================================
        # Attributes (Python <-> QML communication via JSON strings)
        # ==================================================================

        # -- Connection status (read by QML) --
        self.connection_status_attr = self.add_attribute(
            "connection_status",
            json.dumps({
                "connected": False,
                "backend": "",
                "user": "",
                "error": "",
            }),
            {"title": "connection_status"},
            register_as_preference=False,
        )
        self.connection_status_attr.expose_in_ui_attrs_group("Production Tracker")

        # -- Auth configuration (persisted across sessions) --
        self.auth_config_attr = self.add_attribute(
            "auth_config",
            json.dumps({
                "backend": self.config.get("default_backend", "shotgrid"),
                "site_url": "",
                "script_name": "",
                "api_key": "",
                "login": "",
                "password": "",
            }),
            {"title": "auth_config"},
            register_as_preference=True,
        )
        self.auth_config_attr.expose_in_ui_attrs_group("Production Tracker")

        # -- Project list --
        self.projects_data_attr = self.add_attribute(
            "projects_data",
            "[]",
            {"title": "projects_data"},
            register_as_preference=False,
        )
        self.projects_data_attr.expose_in_ui_attrs_group("Production Tracker")

        # -- Selected project (persisted) --
        self.selected_project_attr = self.add_attribute(
            "selected_project",
            json.dumps({"id": -1, "name": ""}),
            {"title": "selected_project"},
            register_as_preference=True,
        )
        self.selected_project_attr.expose_in_ui_attrs_group("Production Tracker")

        # -- Sequences --
        self.sequences_data_attr = self.add_attribute(
            "sequences_data",
            "[]",
            {"title": "sequences_data"},
            register_as_preference=False,
        )
        self.sequences_data_attr.expose_in_ui_attrs_group("Production Tracker")

        # -- Shots --
        self.shots_data_attr = self.add_attribute(
            "shots_data",
            "[]",
            {"title": "shots_data"},
            register_as_preference=False,
        )
        self.shots_data_attr.expose_in_ui_attrs_group("Production Tracker")

        # -- Versions --
        self.versions_data_attr = self.add_attribute(
            "versions_data",
            "[]",
            {"title": "versions_data"},
            register_as_preference=False,
        )
        self.versions_data_attr.expose_in_ui_attrs_group("Production Tracker")

        # -- Command channel (QML -> Python) --
        self.command_attr = self.add_attribute(
            "command_channel",
            "",
            {"title": "command_channel"},
            register_as_preference=False,
        )
        self.command_attr.expose_in_ui_attrs_group("Production Tracker")

        # -- Status / progress message (Python -> QML) --
        self.status_message_attr = self.add_attribute(
            "status_message",
            "",
            {"title": "status_message"},
            register_as_preference=False,
        )
        self.status_message_attr.expose_in_ui_attrs_group("Production Tracker")

        # -- Loading indicator --
        self.loading_attr = self.add_attribute(
            "loading",
            False,
            {"title": "loading"},
            register_as_preference=False,
        )
        self.loading_attr.expose_in_ui_attrs_group("Production Tracker")

        # ==================================================================
        # Hotkey & menu registration
        # ==================================================================

        self.toggle_action = self.register_hotkey(
            self._toggle_panel,
            "T",
            0,          # no modifier
            "Show Production Tracker",
            "Toggles the Production Tracker panel",
            False,      # auto_repeat
            "ProductionTracker",
            "Window",
        )

        self.register_ui_panel_qml(
            "Production Tracker",
            """
            ProductionTracker {
                anchors.fill: parent
            }
            """,
            15.0,
            "",     # no viewport icon
            -1.0,   # no viewport button position
            self.toggle_action,
        )

        # self.insert_menu_item(
        #     "main menu bar",
        #     "Production Tracker",
        #     "View|Panels",
        #     15.0,
        #     hotkey_uuid=self.toggle_action,
        # )

        # ==================================================================
        # Auto-connect with saved credentials
        # ==================================================================
        self._try_auto_connect()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _load_config(self) -> dict:
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        default_config: dict = {"default_backend": "shotgrid"}
        try:
            with open(config_path, "r", encoding="utf-8") as fh:
                cfg = json.load(fh)
                default_config.update(cfg)
        except Exception:
            pass
        return default_config

    # ------------------------------------------------------------------
    # Hotkey callback
    # ------------------------------------------------------------------

    def _toggle_panel(self) -> None:
        # The hotkey system handles panel toggling automatically.
        pass

    # ------------------------------------------------------------------
    # Attribute change handler
    # ------------------------------------------------------------------

    def attribute_changed(self, attribute: Any, role: Any) -> None:
        """Dispatch attribute changes -- primarily the command channel."""

        if attribute.uuid == self.command_attr.uuid and role == AttributeRole.Value:
            try:
                val = self.command_attr.value()
            except TypeError:
                return

            if not val:
                return

            try:
                cmd = json.loads(val)
                _dbg(f"CMD: {cmd}")
                self._handle_command(cmd)
            except Exception as exc:
                _dbg(f"CMD error: {exc}")
                self._set_status(f"Command error: {exc}")
            finally:
                # Clear the command so the next one is detected as a change
                self.command_attr.set_value("")

    # ------------------------------------------------------------------
    # Command dispatcher
    # ------------------------------------------------------------------

    def _handle_command(self, cmd: dict) -> None:
        action = cmd.get("action", "")

        if action == "connect":
            self._connect(cmd.get("config", {}))
        elif action == "disconnect":
            self._disconnect()
        elif action == "refresh_projects":
            self._fetch_projects()
        elif action == "select_project":
            project_id = cmd.get("project_id")
            project_name = cmd.get("project_name", "")
            if project_id is not None:
                self.selected_project_attr.set_value(
                    json.dumps({"id": project_id, "name": project_name})
                )
                self._fetch_sequences(project_id)
        elif action == "select_sequence":
            self._fetch_shots(cmd["project_id"], cmd["sequence_id"])
        elif action == "select_shot":
            self._fetch_versions("Shot", cmd["shot_id"])
        elif action == "add_to_playlist":
            self._add_to_playlist(cmd.get("version_ids", []))
        elif action == "play_selected":
            self._play_selected(cmd.get("version_ids", []))
        elif action == "add_to_timeline":
            self._add_to_timeline(cmd.get("version_ids", []))
        elif action == "compare":
            self._compare_versions(
                cmd.get("version_ids", []),
                cmd.get("mode", "A/B"),
            )
        elif action == "load_versions":
            # Legacy: treat as play_selected
            self._play_selected(cmd.get("version_ids", []))
        elif action == "search":
            self._search_versions(cmd["project_id"], cmd.get("query", ""))
        else:
            _dbg(f"Unknown command action: {action}")

    # ------------------------------------------------------------------
    # Async helper
    # ------------------------------------------------------------------

    def _run_async(self, fn: Any, *args: Any) -> None:
        """Run *fn* in a daemon thread so the UI stays responsive."""

        def _worker() -> None:
            try:
                self.loading_attr.set_value(True)
                fn(*args)
            except Exception as exc:
                _dbg(f"Async error: {exc}")
                traceback.print_exc()
                self._set_status(f"Error: {exc}")
            finally:
                self.loading_attr.set_value(False)

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def _set_status(self, msg: str) -> None:
        _dbg(f"STATUS: {msg}")
        self.status_message_attr.set_value(msg)

    def _set_connection_status(
        self,
        connected: bool,
        backend: str = "",
        user: str = "",
        error: str = "",
    ) -> None:
        self.connection_status_attr.set_value(
            json.dumps({
                "connected": connected,
                "backend": backend,
                "user": user,
                "error": error,
            })
        )

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _connect(self, config: dict) -> None:
        self._run_async(self._do_connect, config)

    def _do_connect(self, config: dict) -> None:
        self._set_status("Connecting...")
        backend_type = config.get("backend", "shotgrid")

        if backend_type == "shotgrid":
            from .shotgrid_backend import ShotGridBackend

            self.backend = ShotGridBackend()
        else:
            self._set_status(f"Unknown backend: {backend_type}")
            self._set_connection_status(False, error=f"Unknown backend: {backend_type}")
            return

        success, error_msg = self.backend.authenticate(
            site_url=config.get("site_url", ""),
            script_name=config.get("script_name", ""),
            api_key=config.get("api_key", ""),
            login=config.get("login", ""),
            password=config.get("password", ""),
        )

        if success:
            # Persist auth config (strip password for security)
            safe_config = dict(config)
            safe_config.pop("password", None)
            self.auth_config_attr.set_value(json.dumps(safe_config))

            self._set_connection_status(
                True,
                backend=self.backend.backend_name,
                user=config.get("login", config.get("script_name", "")),
            )
            self._set_status(f"Connected to {self.backend.backend_name}")
            self._do_fetch_projects()
        else:
            _dbg(f"AUTH FAILED: {error_msg}")
            self._set_connection_status(False, error=error_msg)
            self._set_status(f"Auth failed: {error_msg}")

    def _disconnect(self) -> None:
        if self.backend is not None:
            self.backend.disconnect()
            self.backend = None

        self._set_connection_status(False)
        self.projects_data_attr.set_value("[]")
        self.sequences_data_attr.set_value("[]")
        self.shots_data_attr.set_value("[]")
        self.versions_data_attr.set_value("[]")
        self._set_status("Disconnected")

    def _try_auto_connect(self) -> None:
        """Attempt to reconnect with persisted credentials on startup."""
        try:
            config = json.loads(self.auth_config_attr.value())
            if config.get("site_url") and (
                config.get("api_key") or config.get("login")
            ):
                self._connect(config)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Data fetchers
    # ------------------------------------------------------------------

    def _fetch_projects(self) -> None:
        if not self._check_backend():
            return
        self._run_async(self._do_fetch_projects)

    def _do_fetch_projects(self) -> None:
        self._set_status("Loading projects...")
        projects = self.backend.get_projects()  # type: ignore[union-attr]
        self.projects_data_attr.set_value(json.dumps(projects))
        self._set_status(f"Loaded {len(projects)} project(s)")

    def _fetch_sequences(self, project_id: int) -> None:
        if not self._check_backend():
            return
        self._run_async(self._do_fetch_sequences, project_id)

    def _do_fetch_sequences(self, project_id: int) -> None:
        self._set_status("Loading sequences...")
        sequences = self.backend.get_sequences(project_id)  # type: ignore[union-attr]
        self.sequences_data_attr.set_value(json.dumps(sequences))
        # Clear downstream
        self.shots_data_attr.set_value("[]")
        self.versions_data_attr.set_value("[]")
        self._set_status(f"Loaded {len(sequences)} sequence(s)")

    def _fetch_shots(self, project_id: int, sequence_id: int) -> None:
        if not self._check_backend():
            return
        self._run_async(self._do_fetch_shots, project_id, sequence_id)

    def _do_fetch_shots(self, project_id: int, sequence_id: int) -> None:
        self._set_status("Loading shots...")
        shots = self.backend.get_shots(project_id, sequence_id)  # type: ignore[union-attr]
        self.shots_data_attr.set_value(json.dumps(shots))
        # Clear downstream
        self.versions_data_attr.set_value("[]")
        self._set_status(f"Loaded {len(shots)} shot(s)")

    def _fetch_versions(self, entity_type: str, entity_id: int) -> None:
        if not self._check_backend():
            return
        self._run_async(self._do_fetch_versions, entity_type, entity_id)

    def _do_fetch_versions(self, entity_type: str, entity_id: int) -> None:
        self._set_status("Loading versions...")
        versions = self.backend.get_versions(entity_type, entity_id)  # type: ignore[union-attr]
        self.versions_data_attr.set_value(json.dumps(versions))
        self._set_status(f"Loaded {len(versions)} version(s)")

    def _search_versions(self, project_id: int, query: str) -> None:
        if not self._check_backend():
            return
        self._run_async(self._do_search_versions, project_id, query)

    def _do_search_versions(self, project_id: int, query: str) -> None:
        self._set_status(f"Searching '{query}'...")
        versions = self.backend.search_versions(project_id, query)  # type: ignore[union-attr]
        self.versions_data_attr.set_value(json.dumps(versions))
        self._set_status(f"Found {len(versions)} version(s)")

    # ------------------------------------------------------------------
    # Media actions
    # ------------------------------------------------------------------

    @staticmethod
    def _build_frame_path(frames_path: str, frame_range: str | None) -> str | None:
        """Build an xSTUDIO-compatible path from ShotGrid frame pattern.

        ShotGrid stores paths like:  /path/to/NAME.%04d.exr
        xSTUDIO supports:  /path/to/NAME.%04d.exr=1001-1080
                           /path/to/NAME.####.exr=1001-1080
                           /path/to/NAME.{:04d}.exr=1001-1080
                           /path/to/dir/  (directory scan)

        If we have a frame_range from ShotGrid, append it directly.
        Otherwise fall back to directory scanning.
        """
        import re
        is_pattern = bool(re.search(r'%\d*d|#{2,}|\{[^}]*d\}', frames_path))

        if is_pattern and frame_range:
            # Clean up frame_range: ShotGrid gives "1001-1080" or "1001-1080, 1090-1100"
            clean_range = frame_range.replace(" ", "")
            return f"{frames_path}={clean_range}"

        if is_pattern:
            # No frame range — fall back to directory for scanning
            dir_path = os.path.dirname(frames_path)
            return dir_path if os.path.isdir(dir_path) else None

        # Not a pattern — return as-is (could be a single file)
        return frames_path

    def _resolve_version_paths(self, version_ids: list[int]) -> list[tuple[int, dict, str]]:
        """Resolve version IDs to (id, detail_dict, media_path) tuples.

        Priority: sg_path_to_frames (with frame range) > sg_path_to_movie > SG uploaded movie
        """
        results = []
        for vid in version_ids:
            detail = self.backend.get_version_detail(vid)
            if not detail:
                _dbg(f"No detail for version {vid}")
                continue

            _dbg(f"Version {vid} ({detail.get('code', '?')})")
            _dbg(f"  sg_path_to_frames: {detail.get('sg_path_to_frames')}")
            _dbg(f"  sg_path_to_movie: {detail.get('sg_path_to_movie')}")
            _dbg(f"  frame_range: {detail.get('frame_range')}")

            # Priority 1: Frame sequence with pattern + range
            frames_path = detail.get("sg_path_to_frames")
            if frames_path:
                resolved = self._build_frame_path(
                    frames_path, detail.get("frame_range")
                )
                if resolved:
                    _dbg(f"  -> frames: {resolved}")
                    results.append((vid, detail, resolved))
                    continue
                else:
                    _dbg(f"  -> frames path not resolvable")

            # Priority 2: Local movie file
            movie_path = detail.get("sg_path_to_movie")
            if movie_path:
                # Movie paths are direct file references, not patterns
                if os.path.isfile(movie_path):
                    _dbg(f"  -> movie file: {movie_path}")
                    results.append((vid, detail, movie_path))
                    continue
                else:
                    _dbg(f"  -> movie file not found: {movie_path}")

            # Priority 3: ShotGrid uploaded movie URL
            if self.backend is not None:
                try:
                    url = self.backend.get_movie_url(vid)
                    if url:
                        _dbg(f"  -> SG uploaded movie URL")
                        results.append((vid, detail, url))
                        continue
                except Exception as exc:
                    _dbg(f"  get_movie_url failed: {exc}")

            _dbg(f"  -> NO valid media path found")
        return results

    def _tag_media(self, media, vid: int, detail: dict) -> None:
        """Tag media with ShotGrid metadata."""
        try:
            import json as _json
            meta = {
                "shotgrid": {
                    "version_id": vid,
                    "code": detail.get("code", ""),
                    "status": detail.get("sg_status_list", ""),
                    "entity": detail.get("entity", {}),
                }
            }
            media.set_metadata(_json.dumps(meta), "/metadata/external")
        except Exception as exc:
            _dbg(f"Failed to tag media: {exc}")

    def _get_or_create_playlist(self, name: str = "ShotGrid Review"):
        """Find existing playlist by name or create a new one. Returns Playlist."""
        session = self.connection.api.session
        try:
            for p in session.playlists:
                if p.name == name:
                    return p
        except Exception:
            pass
        _uuid, playlist = session.create_playlist(name)
        return playlist

    # -- Add to Playlist (just adds, doesn't change view) --

    def _add_to_playlist(self, version_ids: list[int]) -> None:
        if not self._check_backend() or not version_ids:
            self._set_status("No versions selected")
            return
        self._run_async(self._do_add_to_playlist, version_ids)

    def _add_media_from_path(self, playlist, path: str):
        """Add media to playlist, handling both directories and files."""
        if os.path.isdir(path):
            _dbg(f"  add_media_list (dir scan): {path}")
            media_list = playlist.add_media_list(path)
            return media_list if media_list else []
        else:
            _dbg(f"  add_media (file): {path}")
            media = playlist.add_media(path)
            return [media] if media else []

    def _do_add_to_playlist(self, version_ids: list[int]) -> None:
        self._set_status(f"Adding {len(version_ids)} version(s) to playlist...")
        resolved = self._resolve_version_paths(version_ids)
        if not resolved:
            self._set_status("No valid media paths found")
            return

        playlist = self._get_or_create_playlist()
        loaded = 0
        for vid, detail, path in resolved:
            try:
                media_list = self._add_media_from_path(playlist, path)
                for media in media_list:
                    self._tag_media(media, vid, detail)
                loaded += len(media_list)
            except Exception as exc:
                _dbg(f"Failed to add {path}: {exc}")
                self._set_status(f"Failed: {path} - {exc}")

        # Switch view to the playlist so user sees the media
        if loaded > 0:
            try:
                session = self.connection.api.session
                session.set_on_screen_source(playlist)
                session.viewed_container = playlist
            except Exception as exc:
                _dbg(f"Failed to switch view: {exc}")

        self._set_status(f"Added {loaded}/{len(version_ids)} to playlist")

    # -- Play Selected (add + view + play) --

    def _play_selected(self, version_ids: list[int]) -> None:
        if not self._check_backend() or not version_ids:
            self._set_status("No versions selected")
            return
        self._run_async(self._do_play_selected, version_ids)

    def _do_play_selected(self, version_ids: list[int]) -> None:
        self._set_status(f"Loading {len(version_ids)} version(s) for playback...")
        resolved = self._resolve_version_paths(version_ids)
        if not resolved:
            self._set_status("No valid media paths found")
            return

        playlist = self._get_or_create_playlist()
        session = self.connection.api.session
        loaded_media = []

        for vid, detail, path in resolved:
            try:
                _dbg(f"PLAY: loading {path}")
                media_list = self._add_media_from_path(playlist, path)
                for media in media_list:
                    self._tag_media(media, vid, detail)
                    loaded_media.append(media)
                    _dbg(f"PLAY: loaded {media.name} uuid={media.uuid}")
            except Exception as exc:
                _dbg(f"PLAY: Failed to load {path}: {exc}")
                traceback.print_exc()

        if loaded_media:
            # Force viewport to display this playlist (must call both)
            try:
                _dbg(f"PLAY: set_on_screen_source({playlist.name})")
                session.set_on_screen_source(playlist)
                _dbg(f"PLAY: set_on_screen_source OK")
            except Exception as exc:
                _dbg(f"PLAY: set_on_screen_source FAILED: {exc}")
                traceback.print_exc()

            try:
                _dbg(f"PLAY: viewed_container = {playlist.name}")
                session.viewed_container = playlist
                _dbg(f"PLAY: viewed_container OK")
            except Exception as exc:
                _dbg(f"PLAY: viewed_container FAILED: {exc}")
                traceback.print_exc()

            # Select the newly loaded media so playhead targets them
            try:
                uuids = [m.uuid for m in loaded_media]
                _dbg(f"PLAY: set_selection({uuids})")
                playlist.playhead_selection.set_selection(uuids)
                _dbg(f"PLAY: set_selection OK")
            except Exception as exc:
                _dbg(f"PLAY: set_selection FAILED: {exc}")
                traceback.print_exc()

            # Start playback
            try:
                _dbg(f"PLAY: playhead.playing = True")
                playlist.playhead.playing = True
                _dbg(f"PLAY: playhead.playing OK")
            except Exception as exc:
                _dbg(f"PLAY: playhead.playing FAILED: {exc}")
                traceback.print_exc()

        self._set_status(f"Playing {len(loaded_media)}/{len(version_ids)} version(s)")

    # -- Add to Timeline (add + create timeline + view) --

    def _add_to_timeline(self, version_ids: list[int]) -> None:
        if not self._check_backend() or not version_ids:
            self._set_status("No versions selected")
            return
        self._run_async(self._do_add_to_timeline, version_ids)

    def _do_add_to_timeline(self, version_ids: list[int]) -> None:
        self._set_status(f"Building timeline from {len(version_ids)} version(s)...")
        resolved = self._resolve_version_paths(version_ids)
        if not resolved:
            self._set_status("No valid media paths found")
            return

        playlist = self._get_or_create_playlist()
        session = self.connection.api.session

        # Add media to playlist first (timeline clips reference playlist media)
        loaded_media = []
        for vid, detail, path in resolved:
            try:
                media_list = self._add_media_from_path(playlist, path)
                for media in media_list:
                    self._tag_media(media, vid, detail)
                    loaded_media.append(media)
            except Exception as exc:
                _dbg(f"Failed to load {path}: {exc}")

        if not loaded_media:
            self._set_status("No media loaded for timeline")
            return

        # Create timeline and populate
        try:
            _uuid, timeline = playlist.create_timeline(
                name="ShotGrid Timeline", with_tracks=True
            )
        except Exception as exc:
            self._set_status(f"Failed to create timeline: {exc}")
            return

        try:
            tracks = timeline.video_tracks
            if tracks:
                track = tracks[0]
                for media in loaded_media:
                    try:
                        track.insert_clip(media)
                    except Exception as exc:
                        _dbg(f"Failed to insert clip: {exc}")
        except Exception as exc:
            _dbg(f"Failed to populate timeline: {exc}")

        # Show the timeline
        try:
            session.set_on_screen_source(timeline)
        except Exception as exc:
            _dbg(f"Failed set_on_screen_source timeline: {exc}")

        try:
            session.viewed_container = timeline
        except Exception as exc:
            _dbg(f"Failed to view timeline: {exc}")

        self._set_status(f"Timeline created with {len(loaded_media)} clip(s)")

    # -- Compare versions --

    def _compare_versions(self, version_ids: list[int], mode: str = "A/B") -> None:
        if not self._check_backend() or not version_ids:
            self._set_status("Select 2+ versions to compare")
            return
        if len(version_ids) < 2:
            self._set_status("Select at least 2 versions to compare")
            return
        self._run_async(self._do_compare_versions, version_ids, mode)

    def _do_compare_versions(self, version_ids: list[int], mode: str) -> None:
        self._set_status(f"Comparing {len(version_ids)} version(s) ({mode})...")
        resolved = self._resolve_version_paths(version_ids)
        if len(resolved) < 2:
            self._set_status("Need at least 2 valid media paths to compare")
            return

        playlist = self._get_or_create_playlist("ShotGrid Compare")
        session = self.connection.api.session
        loaded_media = []

        for vid, detail, path in resolved:
            try:
                media_list = self._add_media_from_path(playlist, path)
                for media in media_list:
                    self._tag_media(media, vid, detail)
                    loaded_media.append(media)
            except Exception as exc:
                _dbg(f"Compare: failed to load {path}: {exc}")

        if len(loaded_media) < 2:
            self._set_status("Could not load enough media to compare")
            return

        # Switch viewport to the compare playlist
        try:
            session.set_on_screen_source(playlist)
            session.viewed_container = playlist
        except Exception as exc:
            _dbg(f"Compare: failed to set view: {exc}")

        # Select all loaded media for comparison
        try:
            uuids = [m.uuid for m in loaded_media]
            playlist.playhead_selection.set_selection(uuids)
        except Exception as exc:
            _dbg(f"Compare: failed to set selection: {exc}")

        # Auto-select best compare mode based on count
        # A/B is best for 2, Grid is better for 3+
        if mode == "auto":
            mode = "A/B" if len(loaded_media) == 2 else "Grid"

        # Set compare mode
        try:
            playlist.playhead.compare_mode = mode
            _dbg(f"Compare: mode set to {mode}")
        except Exception as exc:
            _dbg(f"Compare: failed to set compare_mode: {exc}")

        self._set_status(
            f"Comparing {len(loaded_media)} version(s) — {mode}"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _check_backend(self) -> bool:
        if self.backend is None or not self.backend.is_connected:
            self._set_status("Not connected")
            return False
        return True


# ---------------------------------------------------------------------------
# Entry point (required by xSTUDIO plugin loader)
# ---------------------------------------------------------------------------

def create_plugin_instance(connection: Any) -> ProductionTrackerPlugin:
    return ProductionTrackerPlugin(connection)
