# SPDX-License-Identifier: Apache-2.0

"""HTTP REST API server for xSTUDIO remote control.

Security model:
- Binds to localhost only by default
- API key authentication required (auto-generated if not configured)
- No CORS wildcard -- explicit origin allowlist only
- Path validation blocks UNC paths and validates against allowed roots
- Request body size limited to 1 MB
- All handlers wrapped in exception boundaries
- No tracebacks exposed in HTTP responses
"""

from __future__ import annotations

import hmac
import json
import os
import re
import secrets
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Any

try:
    from xstudio.core import Uuid as XsUuid
except ImportError:
    XsUuid = None

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_BODY_SIZE = 1_048_576  # 1 MB
_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".api_key")


# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------

def _ensure_api_key(configured_key: str) -> str:
    """Return the API key to use.

    Priority: explicit config value > existing key file > newly generated key.
    """
    if configured_key:
        return configured_key

    # Try to read an existing key file
    if os.path.isfile(_KEY_FILE):
        try:
            with open(_KEY_FILE, "r", encoding="utf-8") as fh:
                key = fh.read().strip()
                if key:
                    return key
        except Exception:
            pass

    # Generate a new key and persist it using exclusive create to avoid races
    key = secrets.token_urlsafe(32)
    try:
        fd = os.open(_KEY_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(key)
        print(f"RemoteAPI: generated API key, saved to {_KEY_FILE}")
    except FileExistsError:
        # Another process won the race -- read their key
        with open(_KEY_FILE, "r", encoding="utf-8") as fh:
            key = fh.read().strip()
    except Exception as exc:
        print(f"RemoteAPI: WARNING could not save API key: {exc}")
    return key


def _validate_media_path(
    raw_path: str,
    allowed_roots: list[str],
) -> str | None:
    """Validate and canonicalize a media path.

    Returns the safe path string on success, or ``None`` if the path is
    blocked by policy (UNC path, outside allowed roots, etc.).
    """
    if not raw_path or not isinstance(raw_path, str):
        return None

    # Block UNC paths (Windows network shares)
    if raw_path.startswith("\\\\") or raw_path.startswith("//"):
        return None

    # Separate an optional frame-range suffix (e.g. "=1000-1080")
    range_suffix = ""
    if "=" in raw_path:
        base, maybe_range = raw_path.rsplit("=", 1)
        if re.match(r"^[-0-9x,]+$", maybe_range):
            raw_path = base
            range_suffix = "=" + maybe_range

    # Detect image-sequence patterns (%04d, ####, {frame:04d}, etc.)
    has_pattern = bool(re.search(r"%\d*d|#{2,}|\{[^}]*d\}", raw_path))

    # Canonicalize -- for patterns, check the parent directory instead
    check_path = os.path.dirname(raw_path) if has_pattern else raw_path
    canonical = os.path.realpath(check_path)

    # Re-check for UNC after canonicalization (symlink could resolve to UNC)
    if canonical.startswith("\\\\") or canonical.startswith("//"):
        return None

    # Enforce allowed_roots when configured
    if allowed_roots:
        matched = False
        for root in allowed_roots:
            root_canonical = os.path.realpath(root)
            if canonical == root_canonical or canonical.startswith(
                root_canonical + os.sep
            ):
                matched = True
                break
        if not matched:
            return None

    if has_pattern:
        return os.path.join(canonical, os.path.basename(raw_path)) + range_suffix
    return canonical + range_suffix


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

class XStudioAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler implementing the xSTUDIO REST API."""

    server_version = "xStudioRemoteAPI/1.0"
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.request.settimeout(30)

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    @property
    def api(self) -> Any:
        return self.server.connection.api

    @property
    def session(self) -> Any:
        return self.api.session

    # ------------------------------------------------------------------
    # Response helpers
    # ------------------------------------------------------------------

    def _send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, message: str, status: int = 400) -> None:
        self._send_json({"error": message}, status)

    def _send_cors_headers(self) -> None:
        """Emit CORS headers only when the request Origin is in the allowlist."""
        origin = self.headers.get("Origin", "")
        if origin and origin in self.server.cors_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header(
                "Access-Control-Allow-Methods", "GET, POST, OPTIONS"
            )
            self.send_header(
                "Access-Control-Allow-Headers", "Content-Type, X-API-Key"
            )

    def _read_body(self) -> dict:
        """Read and parse the request body with size enforcement."""
        length_str = self.headers.get("Content-Length", "0")
        try:
            length = int(length_str)
        except (ValueError, TypeError):
            length = 0
        if length == 0:
            return {}
        if length > _MAX_BODY_SIZE:
            raise OverflowError("Request body too large")
        raw = self.rfile.read(length)
        return json.loads(raw)

    def _check_auth(self) -> bool:
        """Verify the API key using constant-time comparison."""
        api_key: str = getattr(self.server, "api_key", "")
        if not api_key:
            return True
        provided = self.headers.get("X-API-Key", "")
        return hmac.compare_digest(provided.encode("utf-8"), api_key.encode("utf-8"))

    # ------------------------------------------------------------------
    # HTTP method dispatchers
    # ------------------------------------------------------------------

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests."""
        try:
            self.send_response(204)
            origin = self.headers.get("Origin", "")
            if origin and origin in self.server.cors_origins:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header(
                    "Access-Control-Allow-Methods", "GET, POST, OPTIONS"
                )
                self.send_header(
                    "Access-Control-Allow-Headers", "Content-Type, X-API-Key"
                )
                self.send_header("Access-Control-Max-Age", "86400")
            self.send_header("Content-Length", "0")
            self.end_headers()
        except Exception:
            pass

    def do_GET(self) -> None:
        try:
            if not self._check_auth():
                return self._send_error_json("Unauthorized", 401)

            path = self.path.split("?")[0].rstrip("/")

            handler = self._GET_ROUTES.get(path)
            if handler is not None:
                handler(self)
            else:
                self._send_error_json("Not found", 404)
        except Exception:
            try:
                self._send_error_json("Internal server error", 500)
            except Exception:
                pass

    def do_POST(self) -> None:
        try:
            if not self._check_auth():
                return self._send_error_json("Unauthorized", 401)

            path = self.path.split("?")[0].rstrip("/")

            try:
                body = self._read_body()
            except OverflowError:
                return self._send_error_json("Request body too large", 413)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return self._send_error_json("Invalid JSON", 400)

            handler = self._POST_ROUTES.get(path)
            if handler is not None:
                handler(self, body)
            else:
                self._send_error_json("Not found", 404)
        except Exception:
            try:
                self._send_error_json("Internal server error", 500)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # GET route handlers
    # ------------------------------------------------------------------

    def _get_docs(self) -> None:
        """GET /api/docs -- Swagger UI for interactive API documentation."""
        html = b"""<!DOCTYPE html>
<html>
<head>
    <title>xSTUDIO API</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
    SwaggerUIBundle({
        url: '/api/openapi.yaml',
        dom_id: '#swagger-ui',
        presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
        layout: "BaseLayout",
        deepLinking: true,
        defaultModelsExpandDepth: 2,
        requestInterceptor: (req) => {
            return req;
        }
    })
    </script>
</body>
</html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(html)

    def _get_openapi_spec(self) -> None:
        """GET /api/openapi.yaml -- Serve the OpenAPI specification."""
        spec_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "openapi.yaml"
        )
        try:
            with open(spec_path, "r", encoding="utf-8") as fh:
                body = fh.read().encode("utf-8")
        except FileNotFoundError:
            return self._send_error_json("OpenAPI spec not found", 404)
        except Exception:
            return self._send_error_json("Failed to read OpenAPI spec", 500)
        self.send_response(200)
        self.send_header("Content-Type", "text/yaml; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _get_status(self) -> None:
        """GET /api/status"""
        version = "unknown"
        try:
            version = str(self.api.app_version)
        except Exception:
            pass

        port = 0
        try:
            port = self.server.server_address[1]
        except Exception:
            pass

        self._send_json({
            "running": True,
            "version": version,
            "api_port": port,
        })

    def _get_session(self) -> None:
        """GET /api/session"""
        playlists = []
        try:
            for p in self.session.playlists:
                media_count = 0
                try:
                    media_count = len(p.media)
                except Exception:
                    pass
                playlists.append({
                    "name": p.name,
                    "uuid": str(p.uuid),
                    "media_count": media_count,
                })
        except Exception:
            pass

        viewed = None
        try:
            vc = self.session.viewed_container
            if vc:
                viewed = {"name": vc.name, "uuid": str(vc.uuid)}
        except Exception:
            pass

        self._send_json({
            "playlists": playlists,
            "viewed_container": viewed,
        })

    def _get_playlists(self) -> None:
        """GET /api/playlists"""
        playlists = []
        try:
            for p in self.session.playlists:
                media_list = []
                try:
                    for m in p.media:
                        entry: dict[str, Any] = {
                            "name": m.name,
                            "uuid": str(m.uuid),
                        }
                        for attr in ("is_online", "flag_colour", "flag_text"):
                            try:
                                entry[attr] = getattr(m, attr)
                            except Exception:
                                pass
                        media_list.append(entry)
                except Exception:
                    pass
                playlists.append({
                    "name": p.name,
                    "uuid": str(p.uuid),
                    "media_count": len(media_list),
                    "media": media_list,
                })
        except Exception:
            return self._send_error_json("Failed to read playlists", 500)

        self._send_json({"playlists": playlists})

    def _get_media(self) -> None:
        """GET /api/media"""
        media_list: list[dict[str, Any]] = []
        try:
            for p in self.session.playlists:
                try:
                    for m in p.media:
                        entry: dict[str, Any] = {
                            "name": m.name,
                            "uuid": str(m.uuid),
                            "playlist": p.name,
                        }
                        for attr in ("is_online", "flag_colour", "flag_text"):
                            try:
                                entry[attr] = getattr(m, attr)
                            except Exception:
                                pass
                        media_list.append(entry)
                except Exception:
                    pass
        except Exception:
            return self._send_error_json("Failed to read media", 500)

        self._send_json({"media": media_list})

    def _get_playhead(self) -> None:
        """GET /api/playhead"""
        try:
            vc = self.session.viewed_container
            if not vc:
                return self._send_json({"error": "No active container"}, 404)

            ph = vc.playhead
            data: dict[str, Any] = {"playing": ph.playing}

            for attr in (
                "position",
                "compare_mode",
                "play_forward",
                "use_loop_range",
                "loop_in_point",
                "loop_out_point",
                "media_frame",
            ):
                try:
                    data[attr] = getattr(ph, attr)
                except Exception:
                    pass

            self._send_json(data)
        except Exception:
            self._send_error_json("Failed to read playhead state", 500)

    def _get_events_stream(self) -> None:
        """GET /api/events -- Server-Sent Events stream at ~4 Hz."""
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self._send_cors_headers()
            self.end_headers()
        except Exception:
            return

        last_state_str: str | None = None
        max_duration = 300  # 5 minutes
        start = time.monotonic()
        try:
            while time.monotonic() - start < max_duration:
                try:
                    state = self._build_state_snapshot()
                    state_str = json.dumps(state, default=str)
                    if state_str != last_state_str:
                        self.wfile.write(
                            f"data: {state_str}\n\n".encode("utf-8")
                        )
                        self.wfile.flush()
                        last_state_str = state_str
                except (
                    BrokenPipeError,
                    ConnectionResetError,
                    ConnectionAbortedError,
                    OSError,
                ):
                    break
                except Exception:
                    # Tolerate transient xSTUDIO API errors
                    pass
                time.sleep(0.25)
            # Tell client to reconnect after timeout
            try:
                self.wfile.write(b"event: timeout\ndata: {\"reconnect\": true}\n\n")
                self.wfile.flush()
            except Exception:
                pass
        except (
            BrokenPipeError,
            ConnectionResetError,
            ConnectionAbortedError,
            OSError,
        ):
            pass

    def _build_state_snapshot(self) -> dict[str, Any]:
        """Build a lightweight state snapshot for SSE."""
        state: dict[str, Any] = {"timestamp": time.time()}
        try:
            vc = self.session.viewed_container
            if vc:
                state["viewed_container"] = {
                    "name": vc.name,
                    "uuid": str(vc.uuid),
                }
                try:
                    ph = vc.playhead
                    playhead_data: dict[str, Any] = {"playing": ph.playing}
                    for attr in ("position", "compare_mode", "media_frame"):
                        try:
                            playhead_data[attr] = getattr(ph, attr)
                        except Exception:
                            pass
                    state["playhead"] = playhead_data
                except Exception:
                    pass
        except Exception:
            pass
        return state

    # ------------------------------------------------------------------
    # POST route handlers
    # ------------------------------------------------------------------

    def _get_active_playhead(self) -> Any | None:
        """Get playhead from currently viewed container, or None."""
        try:
            vc = self.session.viewed_container
            if vc:
                return vc.playhead
        except Exception:
            pass
        return None

    def _require_playhead(self) -> Any | None:
        """Get active playhead or send 404 error. Returns playhead or None."""
        ph = self._get_active_playhead()
        if ph is None:
            self._send_error_json("No active playhead - view a playlist first", 404)
        return ph

    def _playhead_play(self, body: dict) -> None:
        """POST /api/playhead/play"""
        ph = self._require_playhead()
        if not ph:
            return
        try:
            ph.playing = True
            self._send_json({"playing": True})
        except Exception:
            self._send_error_json("Failed to start playback", 500)

    def _playhead_pause(self, body: dict) -> None:
        """POST /api/playhead/pause"""
        ph = self._require_playhead()
        if not ph:
            return
        try:
            ph.playing = False
            self._send_json({"playing": False})
        except Exception:
            self._send_error_json("Failed to pause playback", 500)

    def _playhead_toggle(self, body: dict) -> None:
        """POST /api/playhead/toggle"""
        ph = self._require_playhead()
        if not ph:
            return
        try:
            ph.playing = not ph.playing
            self._send_json({"playing": ph.playing})  # read back actual state
        except Exception:
            self._send_error_json("Failed to toggle playback", 500)

    def _playhead_seek(self, body: dict) -> None:
        """POST /api/playhead/seek -- Body: {"frame": <int>}"""
        frame = body.get("frame")
        if frame is None:
            return self._send_error_json("'frame' is required", 400)
        try:
            frame = int(frame)
        except (ValueError, TypeError):
            return self._send_error_json("'frame' must be an integer", 400)
        ph = self._require_playhead()
        if not ph:
            return
        try:
            ph.position = frame
            self._send_json({"position": frame})
        except Exception:
            self._send_error_json("Failed to seek", 500)

    def _playhead_step(self, body: dict) -> None:
        """POST /api/playhead/step -- Body: {"frames": <int>}"""
        try:
            frames = int(body.get("frames", 1))
        except (ValueError, TypeError):
            return self._send_error_json("'frames' must be an integer", 400)
        ph = self._require_playhead()
        if not ph:
            return
        try:
            new_pos = ph.position + frames
            ph.position = new_pos
            self._send_json({"position": new_pos})
        except Exception:
            self._send_error_json("Failed to step", 500)

    def _playhead_compare(self, body: dict) -> None:
        """POST /api/playhead/compare -- Body: {"mode": "A/B"|"Grid"|"Over"|"Off"}"""
        mode = body.get("mode", "Off")
        ph = self._require_playhead()
        if not ph:
            return
        try:
            ph.compare_mode = mode
            self._send_json({"compare_mode": mode})
        except Exception:
            self._send_error_json("Failed to set compare mode", 500)

    def _playhead_loop(self, body: dict) -> None:
        """POST /api/playhead/loop -- Body: {"enabled": bool, "in": int, "out": int}"""
        ph = self._require_playhead()
        if not ph:
            return
        if "in" in body:
            try:
                body["in"] = int(body["in"])
            except (ValueError, TypeError):
                return self._send_error_json("'in' must be an integer", 400)
        if "out" in body:
            try:
                body["out"] = int(body["out"])
            except (ValueError, TypeError):
                return self._send_error_json("'out' must be an integer", 400)
        try:
            if "enabled" in body:
                ph.use_loop_range = bool(body["enabled"])
            if "in" in body:
                ph.loop_in_point = body["in"]
            if "out" in body:
                ph.loop_out_point = body["out"]

            result: dict[str, Any] = {}
            for attr in ("use_loop_range", "loop_in_point", "loop_out_point"):
                try:
                    result[attr] = getattr(ph, attr)
                except Exception:
                    pass
            self._send_json(result)
        except Exception:
            self._send_error_json("Failed to set loop range", 500)

    def _media_add(self, body: dict) -> None:
        """POST /api/media/add -- Body: {"path": "...", "playlist": "name"}

        Either ``path`` (single string) or ``paths`` (list) is accepted.
        Defaults to creating / using a playlist called "Remote API".
        """
        path = body.get("path")
        paths = body.get("paths", [])
        playlist_name = body.get("playlist", "Remote API")

        if path:
            paths = [path]
        if not paths:
            return self._send_error_json("'path' or 'paths' is required")

        # Validate every path before touching the session
        allowed_roots: list[str] = getattr(self.server, "allowed_roots", [])
        validated: list[str] = []
        rejected: list[str] = []
        for p in paths:
            safe = _validate_media_path(p, allowed_roots)
            if safe is not None:
                validated.append(safe)
            else:
                rejected.append(p)

        if not validated:
            return self._send_error_json(
                "All paths were rejected by path validation", 403
            )

        session = self.session

        # Find or create the target playlist
        playlist = None
        try:
            for pl in session.playlists:
                if pl.name == playlist_name:
                    playlist = pl
                    break
        except Exception:
            pass

        if playlist is None:
            _uuid, playlist = session.create_playlist(playlist_name)

        loaded: list[dict[str, Any]] = []
        for media_path in validated:
            try:
                if os.path.isdir(media_path):
                    media_list = playlist.add_media_list(media_path)
                    for m in media_list or []:
                        loaded.append({"name": m.name, "uuid": str(m.uuid)})
                else:
                    m = playlist.add_media(media_path)
                    if m:
                        loaded.append({"name": m.name, "uuid": str(m.uuid)})
            except Exception:
                loaded.append({"error": "Failed to load", "path": media_path})

        # Report rejected paths
        for rp in rejected:
            loaded.append({"error": "Path blocked by policy", "path": rp})

        # Switch viewport to show the playlist
        try:
            session.set_on_screen_source(playlist)
            session.viewed_container = playlist
        except Exception:
            pass

        success_count = len([item for item in loaded if "uuid" in item])
        self._send_json({
            "loaded": loaded,
            "count": success_count,
            "playlist": playlist_name,
        })

    def _playlist_create(self, body: dict) -> None:
        """POST /api/playlist/create -- Body: {"name": "My Playlist"}"""
        name = body.get("name", "New Playlist")
        _uuid, playlist = self.session.create_playlist(name)
        self._send_json({
            "name": playlist.name,
            "uuid": str(playlist.uuid),
        })

    def _playlist_view(self, body: dict) -> None:
        """POST /api/playlist/view -- Body: {"name": "..."} or {"uuid": "..."}"""
        name = body.get("name")
        uuid_str = body.get("uuid")

        if not name and not uuid_str:
            return self._send_error_json("'name' or 'uuid' is required")

        session = self.session
        target = None

        try:
            for p in session.playlists:
                if name and p.name == name:
                    target = p
                    break
                if uuid_str and str(p.uuid) == uuid_str:
                    target = p
                    break
        except Exception:
            pass

        if not target:
            return self._send_error_json("Playlist not found", 404)

        session.set_on_screen_source(target)
        session.viewed_container = target
        self._send_json({
            "viewed": {"name": target.name, "uuid": str(target.uuid)},
        })

    def _playlist_select(self, body: dict) -> None:
        """POST /api/playlist/select -- Body: {"uuids": ["uuid-1", ...]}"""
        uuids = body.get("uuids", [])
        if not uuids:
            return self._send_error_json("'uuids' is required")

        vc = self.session.viewed_container
        if not vc:
            return self._send_error_json("No active container", 404)

        if XsUuid is None:
            return self._send_error_json("xstudio.core not available", 500)
        xs_uuids = []
        for u in uuids:
            try:
                xs_uuids.append(XsUuid(u))
            except Exception:
                pass

        if xs_uuids:
            try:
                vc.playhead_selection.set_selection(xs_uuids)
            except Exception:
                return self._send_error_json("Selection failed", 500)

        self._send_json({"selected": len(xs_uuids)})

    # ------------------------------------------------------------------
    # Route tables
    # ------------------------------------------------------------------

    _GET_ROUTES: dict[str, Any] = {
        "/api/docs": _get_docs,
        "/api/openapi.yaml": _get_openapi_spec,
        "/api/status": _get_status,
        "/api/session": _get_session,
        "/api/playlists": _get_playlists,
        "/api/media": _get_media,
        "/api/playhead": _get_playhead,
        "/api/events": _get_events_stream,
    }

    _POST_ROUTES: dict[str, Any] = {
        "/api/playhead/play": _playhead_play,
        "/api/playhead/pause": _playhead_pause,
        "/api/playhead/toggle": _playhead_toggle,
        "/api/playhead/seek": _playhead_seek,
        "/api/playhead/step": _playhead_step,
        "/api/playhead/compare": _playhead_compare,
        "/api/playhead/loop": _playhead_loop,
        "/api/media/add": _media_add,
        "/api/playlist/create": _playlist_create,
        "/api/playlist/view": _playlist_view,
        "/api/playlist/select": _playlist_select,
    }

    # ------------------------------------------------------------------
    # Suppress noisy HTTP logs
    # ------------------------------------------------------------------

    def log_message(self, format: str, *args: Any) -> None:
        pass


# ---------------------------------------------------------------------------
# Server factory
# ---------------------------------------------------------------------------

def create_server(
    connection: Any,
    port: int = 45678,
    bind: str = "127.0.0.1",
    api_key: str = "",
    cors_origins: list[str] | None = None,
    allowed_roots: list[str] | None = None,
) -> ThreadingHTTPServer:
    """Create and configure the threaded HTTP server.

    Parameters
    ----------
    connection
        The xSTUDIO plugin connection object.
    port
        TCP port to listen on (default 45678).
    bind
        Address to bind to (default ``127.0.0.1`` -- localhost only).
    api_key
        Explicit API key.  If empty, one is auto-generated and persisted
        to a ``.api_key`` file next to this module.
    cors_origins
        List of allowed CORS origins (e.g. ``["http://localhost:3000"]``).
        An empty list means no CORS headers are emitted at all.
    allowed_roots
        List of filesystem roots that ``/api/media/add`` is allowed to
        load from.  An empty list means any local path is accepted
        (UNC paths are always blocked regardless).
    """
    server = ThreadingHTTPServer((bind, port), XStudioAPIHandler)
    server.connection = connection  # type: ignore[attr-defined]
    server.api_key = _ensure_api_key(api_key)  # type: ignore[attr-defined]
    server.cors_origins = cors_origins or []  # type: ignore[attr-defined]
    server.allowed_roots = allowed_roots or []  # type: ignore[attr-defined]
    server.socket.settimeout(10)  # Prevent slowloris attacks
    return server
