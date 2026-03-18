# SPDX-License-Identifier: Apache-2.0

"""Remote API plugin for xSTUDIO.

Exposes a REST/HTTP API on a configurable port, enabling AI agents, scripts,
and other xSTUDIO instances to control playback, load media, and query
session state over HTTP.

Uses only Python stdlib (http.server, json, threading) -- no external
dependencies required.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from typing import Any

from xstudio.plugin import PluginBase


# ---------------------------------------------------------------------------
# Debug logging (file-based, same pattern as other xSTUDIO Python plugins)
# ---------------------------------------------------------------------------

_DEBUG_LOG = os.path.join(tempfile.gettempdir(), "xstudio_remote_api_debug.txt")


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

class RemoteAPIPlugin(PluginBase):
    """xSTUDIO Python plugin that runs a REST/HTTP server for remote control."""

    def __init__(self, connection: Any) -> None:
        PluginBase.__init__(self, connection, "Remote API")

        self.config = self._load_config()
        self.server = None
        self.server_thread = None

        # ------------------------------------------------------------------
        # Attributes (expose server status to the UI)
        # ------------------------------------------------------------------

        self.api_status_attr = self.add_attribute(
            "api_status",
            json.dumps({"running": False, "port": 0, "url": ""}),
            {"title": "api_status"},
            register_as_preference=False,
        )
        self.api_status_attr.expose_in_ui_attrs_group("Remote API")

        # ------------------------------------------------------------------
        # Start the HTTP server
        # ------------------------------------------------------------------
        self._start_server()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _load_config(self) -> dict:
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        default_config: dict = {
            "port": 45678,
            "bind_address": "127.0.0.1",
            "api_key": "",
            "cors_origins": [],
            "allowed_roots": [],
        }
        try:
            with open(config_path, "r", encoding="utf-8") as fh:
                cfg = json.load(fh)
                default_config.update(cfg)
        except Exception:
            pass
        return default_config

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------

    def _start_server(self) -> None:
        """Start the HTTP server in a daemon thread."""
        from .server import create_server

        port = self.config.get("port", 45678)
        bind = self.config.get("bind_address", "127.0.0.1")
        api_key = self.config.get("api_key", "")

        cors_origins = self.config.get("cors_origins", [])
        allowed_roots = self.config.get("allowed_roots", [])

        try:
            self.server = create_server(
                self.connection, port, bind, api_key,
                cors_origins=cors_origins,
                allowed_roots=allowed_roots,
            )
            self.server_thread = threading.Thread(
                target=self.server.serve_forever,
                daemon=True,
                name="RemoteAPI-HTTP",
            )
            self.server_thread.start()

            url = f"http://{bind}:{port}"
            self.api_status_attr.set_value(json.dumps({
                "running": True,
                "port": port,
                "url": url,
            }))
            _dbg(f"RemoteAPI: listening on {url}")
            print(f"RemoteAPI: listening on {url}")

        except Exception as exc:
            error_msg = f"RemoteAPI: failed to start server: {exc}"
            _dbg(error_msg)
            print(error_msg)
            self.api_status_attr.set_value(json.dumps({
                "running": False,
                "port": port,
                "url": "",
                "error": str(exc),
            }))

    def destroy(self) -> None:
        """Clean shutdown when the plugin is unloaded."""
        if self.server is not None:
            try:
                self.server.shutdown()
                _dbg("RemoteAPI: server shut down")
            except Exception as exc:
                _dbg(f"RemoteAPI: shutdown error: {exc}")
        self.server = None
        self.server_thread = None


# ---------------------------------------------------------------------------
# Entry point (required by xSTUDIO plugin loader)
# ---------------------------------------------------------------------------

def create_plugin_instance(connection: Any) -> RemoteAPIPlugin:
    return RemoteAPIPlugin(connection)
