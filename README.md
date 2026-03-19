# xSTUDIO (Windows Fork)

Professional media playback and review tool for VFX/film post-production. GPU-accelerated OpenGL viewport, EXR/FFmpeg media readers, timeline editing, and a plugin architecture built on the C++ Actor Framework (CAF) and Qt6.

This is a fork of [AcademySoftwareFoundation/xstudio](https://github.com/AcademySoftwareFoundation/xstudio) with Windows platform support, production pipeline integration, and performance improvements. See the upstream repository for full project documentation and Linux build instructions.

### Known Issues (upstream)

- Moderate audio distortion on playback (Windows only)
- User documentation and API documentation is out of date

---

## What Changed

### Build and Infrastructure

| Change | Detail |
|--------|--------|
| Windows build support | CMakePresets for Visual Studio 17 2022 with vcpkg and Qt 6.5.3 |
| Cross-platform scripts | `build.bat` (Windows) and `build.sh` (Linux/macOS) |
| Issue tracking | Beads (`bd`) integration for local issue management |

### Core Bug Fixes

- **Session restore on Windows** -- Fixed 5 path-handling bugs: drive letter case normalization, `file://` URI format, variable naming collision, timeline population from saved state, container type mismatch.
- **Windows path handling** -- Backslash regex escaping, `pad_size` returning 0 for Windows paths, URI normalization for mixed separators.
- **Hierarchical EXR channels** -- Fixed "Unable to choose decoder routines" crash for multi-level channel names like `bg_wall.Combined.R`.

### Performance

- **EXR read pipeline** -- Cached JSON headers, cached `MultiPartInputFile` handles, batched precache checks, `max_in_flight` raised from 4 to 8.
- **Configurable decompression threads** -- EXR thread count (default 16) is now a runtime setting.
- **Concurrent precache** -- Up to 4 simultaneous precache requests.
- **Benchmark tool** -- Standalone EXR read benchmark in `bench/exr_benchmark/`.

### New Features

- **Printf frame patterns** -- `%04d`, `####`, and `{:04d}` all work. Nuke-style space-separated ranges (`file.%04d.exr 1000-1080`) are supported.
- **Review mode** -- `--review` / `-v` CLI flag for a minimal presentation layout.
- **Viewport drag-drop** -- Drop media files onto the viewport in any layout mode.
- **Hotkey editor** -- Interactive key rebinding with conflict detection and persistence.
- **EXR layer/AOV selector** -- Dropdown in the viewport toolbar for selecting render layers.
- **Gamma/saturation controls** -- Visible by default in the viewport toolbar.

### Timeline

- Alt+wheel zoom centered on cursor, Shift+Z zoom-to-fit, Ctrl+wheel zoom
- Clip drag handles appear on hover
- Drag-drop from browser to timeline
- "Add to Timeline" context menu entry
- Compare Items: A/B and Grid compare modes

### New Plugins

**Filesystem Browser** -- Hierarchical directory tree with favorites, file sequence detection, version grouping, multi-select, thumbnail generation, drag-drop into timeline, and Windows-specific drive enumeration with case-insensitive path handling.

**Production Tracker (ShotGrid)** -- ShotGrid authentication via script API key or user login. Browse Projects, Sequences, Shots, Versions. Five media actions: Add to Playlist, Play, Add to Timeline, A/B Compare, Grid Compare. Abstract `TrackerBackend` interface for future Ftrack/Flow integration. Auto-reconnect with persisted credentials. Bundles vendored `shotgun_api3`.

**Remote API (REST/HTTP)** -- HTTP server on `localhost:45678` for programmatic control. 17 endpoints for session state, playback, and media loading. See the [REST API Reference](#rest-api-reference) below.

---

## Building on Windows

### Prerequisites

- Visual Studio 2022 (v17)
- CMake 3.24+
- [vcpkg](https://github.com/microsoft/vcpkg) cloned alongside xstudio (i.e., `../vcpkg/`)
- Qt 6.5.3 installed to `C:/Qt/6.5.3/msvc2019_64/`

### Configure and Build

```bash
cmake --preset WinRelease
cmake --build build --config Release --target xstudio
```

Other presets: `WinRelWithDebInfo` (AddressSanitizer enabled), `WinDebug`.

### Portable Deployment

The application runs from the `portable/` directory. After building, copy updated outputs:

```bash
# Core binaries
cp build/bin/Release/xstudio.exe portable/bin/
cp build/src/colour_pipeline/src/Release/colour_pipeline.dll portable/bin/
cp build/src/module/src/Release/module.dll portable/bin/

# Plugins (MUST go to plugin/, not bin/)
cp build/src/plugin/colour_pipeline/ocio/src/Release/colour_pipeline_ocio.dll portable/share/xstudio/plugin/
cp build/src/plugin/media_reader/openexr/src/Release/media_reader_openexr.dll portable/share/xstudio/plugin/
cp build/src/plugin/media_reader/ffmpeg/src/Release/media_reader_ffmpeg.dll portable/share/xstudio/plugin/
```

Launch: `portable/bin/xstudio.exe`

---

## GitHub Releases

The repo now includes a native multi-platform release workflow in [`.github/workflows/release-builds.yml`](.github/workflows/release-builds.yml).

- Publishing a GitHub release builds and uploads Windows, Linux, and macOS artifacts.
- Manual runs via `workflow_dispatch` build the same artifacts and keep them as workflow artifacts; if you provide an existing `release_tag`, the workflow also uploads them to that release.
- Windows uses the existing NSIS `PACKAGE` target.
- macOS publishes both Apple Silicon and Intel zip archives using `xstudio_macos_zip`.
- Linux currently publishes an installed-tree `.tar.gz` rather than a fully self-contained AppImage or distro package.
- To watch a run locally, use `gh run watch <run-id>`.
- Optional Discord notifications are supported by setting the repository secret `DISCORD_WEBHOOK_URL`; the workflow posts one final success/failure message after the full matrix settles.

### Release Caveats

- macOS release automation currently produces unsigned/ad-hoc archives unless you add signing and notarization credentials to CI.
- Linux packaging is good for build validation and internal distribution, but it still needs a dedicated self-contained packaging path for broader end-user release distribution.

---

## REST API Reference

The Remote API plugin starts an HTTP server on `localhost:45678`. All requests require an `X-API-Key` header. The key is auto-generated on first launch and written to a `.api_key` file in the plugin directory.

### Authentication

Every request must include the API key:

```
X-API-Key: <your-key>
```

Read the key from the file:

```bash
API_KEY=$(cat portable/share/xstudio/plugin-python/remote_api/.api_key)
```

### Security Model

- Binds to `127.0.0.1` only (localhost)
- API key verified with constant-time comparison
- CORS restricted to an explicit origin allowlist (no wildcards)
- `POST /api/media/add` validates paths against allowed roots; UNC paths are always blocked
- Request body limited to 10 MB
- No stack traces in error responses

### Endpoints

#### GET

| Endpoint | Description |
|----------|-------------|
| `/api/status` | Server status and xSTUDIO version |
| `/api/session` | Playlist list with media counts, currently viewed container |
| `/api/playlists` | All playlists with full media listings (name, uuid, flags) |
| `/api/media` | Flat list of all media across all playlists |
| `/api/playhead` | Playback state: playing, position, compare mode, loop range |
| `/api/events` | SSE stream at ~4 Hz, emits state diffs for 5 minutes then reconnect |
| `/api/docs` | Interactive Swagger UI |
| `/api/openapi.yaml` | OpenAPI 3.0 specification |

#### POST

| Endpoint | Body | Description |
|----------|------|-------------|
| `/api/playhead/play` | `{}` | Start playback |
| `/api/playhead/pause` | `{}` | Pause playback |
| `/api/playhead/toggle` | `{}` | Toggle play/pause |
| `/api/playhead/seek` | `{"frame": int}` | Seek to frame number |
| `/api/playhead/step` | `{"frames": int}` | Step forward/backward by N frames |
| `/api/playhead/compare` | `{"mode": "A/B"\|"Grid"\|"Over"\|"Off"}` | Set compare mode |
| `/api/playhead/loop` | `{"enabled": bool, "in": int, "out": int}` | Set loop range |
| `/api/media/add` | `{"path": "..."} or {"paths": [...]}` | Load media into a playlist |
| `/api/playlist/create` | `{"name": "..."}` | Create a new playlist |
| `/api/playlist/view` | `{"name": "..."} or {"uuid": "..."}` | Switch viewport to a playlist |
| `/api/playlist/select` | `{"uuids": ["...", ...]}` | Select specific media items |
| `/api/timeline/create` | `{"name": "...", "paths": [...], "media_uuids": [...]}` | Create a timeline with optional clips |

### Quick Start

```bash
# Store the API key
API_KEY=$(cat portable/share/xstudio/plugin-python/remote_api/.api_key)

# Check status
curl -s -H "X-API-Key: $API_KEY" http://localhost:45678/api/status

# Load an EXR sequence
curl -s -X POST -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"path": "L:/tdm/shots/fw/9119/comp/images/FW9119_comp_v001/exr"}' \
  http://localhost:45678/api/media/add

# Start playback
curl -s -X POST -H "X-API-Key: $API_KEY" \
  http://localhost:45678/api/playhead/play

# Seek to frame 1050
curl -s -X POST -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"frame": 1050}' \
  http://localhost:45678/api/playhead/seek

# Get current playhead state
curl -s -H "X-API-Key: $API_KEY" http://localhost:45678/api/playhead

# Listen for state changes (SSE stream)
curl -s -N -H "X-API-Key: $API_KEY" http://localhost:45678/api/events

# Create a playlist and load media into it
curl -s -X POST -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "Review Session"}' \
  http://localhost:45678/api/playlist/create

curl -s -X POST -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"path": "/path/to/media.exr", "playlist": "Review Session"}' \
  http://localhost:45678/api/media/add

# A/B compare mode
curl -s -X POST -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"mode": "A/B"}' \
  http://localhost:45678/api/playhead/compare
```

### POST /api/media/add Details

Accepts either `"path"` (single string) or `"paths"` (array of strings). If a path points to a directory, all recognized media sequences in that directory are loaded. The optional `"playlist"` field names the target playlist (defaults to `"Remote API"`). If the playlist does not exist, it is created automatically.

Response:

```json
{
  "loaded": [
    {"name": "FW9119_comp_v001", "uuid": "abc-123"},
    {"error": "Path blocked by policy", "path": "\\\\server\\share\\file.exr"}
  ],
  "count": 1,
  "playlist": "Remote API"
}
```

### SSE Event Stream

`GET /api/events` opens a Server-Sent Events connection. The server emits a `data:` line whenever playback state changes, at up to 4 Hz. After 5 minutes the server sends a `timeout` event; the client should reconnect.

Example event:

```json
{
  "timestamp": 1710700000.0,
  "viewed_container": {"name": "My Playlist", "uuid": "..."},
  "playhead": {"playing": true, "position": 1042, "compare_mode": "Off"}
}
```

---

## License

Apache-2.0 -- same as upstream xSTUDIO.
