# xSTUDIO Remote API Guide

Control xSTUDIO over HTTP from scripts, pipeline tools, or web dashboards. The
Remote API plugin exposes a REST interface on `localhost:45678` with Server-Sent
Events for real-time state updates.

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Authentication](#2-authentication)
3. [Checking Status](#3-checking-status)
4. [Controlling Playback](#4-controlling-playback)
5. [Loading Media](#5-loading-media)
6. [Managing Playlists](#6-managing-playlists)
7. [Real-Time Events (SSE)](#7-real-time-events-sse)
8. [Multi-Instance Sync](#8-multi-instance-sync-preview)
9. [Configuration](#9-configuration)
10. [Troubleshooting](#10-troubleshooting)

---

## Endpoint Summary

### GET Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/status` | Check if xSTUDIO is running |
| `GET /api/session` | Get current session overview |
| `GET /api/playlists` | List all playlists with media details |
| `GET /api/media` | List all media across all playlists |
| `GET /api/playhead` | Get current playback state |
| `GET /api/events` | Server-Sent Events stream |

### POST Endpoints

| Endpoint | Description |
|---|---|
| `POST /api/playhead/play` | Start playback |
| `POST /api/playhead/pause` | Pause playback |
| `POST /api/playhead/toggle` | Toggle play/pause |
| `POST /api/playhead/seek` | Jump to a specific frame |
| `POST /api/playhead/step` | Step forward or backward by N frames |
| `POST /api/playhead/compare` | Set compare mode (A/B, Grid, etc.) |
| `POST /api/playhead/loop` | Configure loop range |
| `POST /api/media/add` | Load media files or directories |
| `POST /api/playlist/create` | Create a new playlist |
| `POST /api/playlist/view` | Switch viewport to a playlist |
| `POST /api/playlist/select` | Select specific media for comparison |

---

## 1. Quick Start

The API key is auto-generated on first launch and saved to a file next to the
plugin:

```
portable/share/xstudio/plugin-python/remote_api/.api_key
```

Open that file and copy the key. Then test:

```bash
curl -s -H "X-API-Key: YOUR_KEY" http://localhost:45678/api/status
```

Expected response:

```json
{
  "running": true,
  "version": "0.5.0",
  "api_port": 45678
}
```

If you get that back, the API is working and you can control xSTUDIO from any
HTTP client.

---

## 2. Authentication

Every request must include the API key in the `X-API-Key` header. Requests
without a valid key receive a `401 Unauthorized` response.

The key is resolved in this order:

1. Explicit value in `config.json` (the `api_key` field)
2. Existing `.api_key` file in the plugin directory
3. Auto-generated and saved to `.api_key` on first run

### curl

```bash
curl -H "X-API-Key: YOUR_KEY" http://localhost:45678/api/status
```

### Python (requests)

```python
import requests

API_KEY = "YOUR_KEY"
BASE = "http://localhost:45678"
HEADERS = {"X-API-Key": API_KEY}

r = requests.get(f"{BASE}/api/status", headers=HEADERS)
print(r.json())
```

### JavaScript (fetch)

```javascript
const API_KEY = "YOUR_KEY";
const BASE = "http://localhost:45678";

const resp = await fetch(`${BASE}/api/status`, {
  headers: { "X-API-Key": API_KEY }
});
const data = await resp.json();
console.log(data);
```

---

## 3. Checking Status

### GET /api/status

Returns whether xSTUDIO is running and which port the API is on.

```bash
curl -s -H "X-API-Key: $KEY" http://localhost:45678/api/status
```

```json
{
  "running": true,
  "version": "0.5.0",
  "api_port": 45678
}
```

### GET /api/session

Returns the current session state: all playlists and which one is currently
displayed in the viewport.

```bash
curl -s -H "X-API-Key: $KEY" http://localhost:45678/api/session
```

```json
{
  "playlists": [
    {
      "name": "Comp Review",
      "uuid": "a1b2c3d4-...",
      "media_count": 12
    }
  ],
  "viewed_container": {
    "name": "Comp Review",
    "uuid": "a1b2c3d4-..."
  }
}
```

```python
r = requests.get(f"{BASE}/api/session", headers=HEADERS)
session = r.json()
for pl in session["playlists"]:
    print(f"{pl['name']}: {pl['media_count']} items")
```

---

## 4. Controlling Playback

All playback endpoints are POST requests that operate on the currently viewed
playlist's playhead. If no playlist is viewed, they return `404`.

### GET /api/playhead -- Read Current State

```bash
curl -s -H "X-API-Key: $KEY" http://localhost:45678/api/playhead
```

```json
{
  "playing": false,
  "position": 1024,
  "compare_mode": "Off",
  "play_forward": true,
  "use_loop_range": false,
  "loop_in_point": 1000,
  "loop_out_point": 1080,
  "media_frame": 24
}
```

### Play, Pause, Toggle

These take no body. Send an empty POST.

```bash
# Start playback
curl -s -X POST -H "X-API-Key: $KEY" http://localhost:45678/api/playhead/play

# Pause
curl -s -X POST -H "X-API-Key: $KEY" http://localhost:45678/api/playhead/pause

# Toggle (play if paused, pause if playing)
curl -s -X POST -H "X-API-Key: $KEY" http://localhost:45678/api/playhead/toggle
```

```python
# Toggle playback
r = requests.post(f"{BASE}/api/playhead/toggle", headers=HEADERS)
print(r.json())  # {"playing": true}
```

Response for all three:

```json
{"playing": true}
```

### Seek to a Specific Frame

Jump the playhead to an absolute frame number.

```bash
curl -s -X POST \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"frame": 1050}' \
  http://localhost:45678/api/playhead/seek
```

```python
requests.post(f"{BASE}/api/playhead/seek",
              headers=HEADERS,
              json={"frame": 1050})
```

```json
{"position": 1050}
```

### Step Forward or Backward

Move the playhead by a relative number of frames. Positive values step forward,
negative values step backward. Defaults to 1 if `frames` is omitted.

```bash
# Step forward 5 frames
curl -s -X POST \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"frames": 5}' \
  http://localhost:45678/api/playhead/step

# Step backward 1 frame
curl -s -X POST \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"frames": -1}' \
  http://localhost:45678/api/playhead/step
```

```python
# Step backward 10 frames
requests.post(f"{BASE}/api/playhead/step",
              headers=HEADERS,
              json={"frames": -10})
```

```json
{"position": 1040}
```

### Set Compare Mode

Switch between comparison layouts. Valid modes:

| Mode | Use Case |
|---|---|
| `"Off"` | Single image, no comparison |
| `"A/B"` | Side-by-side wipe between two versions |
| `"Grid"` | Tile multiple versions in a grid |
| `"Over"` | Overlay with transparency |

```bash
curl -s -X POST \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"mode": "A/B"}' \
  http://localhost:45678/api/playhead/compare
```

```python
# Use Grid mode to compare 3+ versions
requests.post(f"{BASE}/api/playhead/compare",
              headers=HEADERS,
              json={"mode": "Grid"})
```

```json
{"compare_mode": "A/B"}
```

### Set Loop Range

Restrict playback to a frame range. All fields are optional -- you can enable
the loop, set the range, or do both at once.

| Field | Type | Description |
|---|---|---|
| `enabled` | bool | Turn looping on or off |
| `in` | int | Loop start frame |
| `out` | int | Loop end frame |

```bash
# Set a loop range and enable it
curl -s -X POST \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "in": 1010, "out": 1050}' \
  http://localhost:45678/api/playhead/loop
```

```python
# Enable looping on the existing range
requests.post(f"{BASE}/api/playhead/loop",
              headers=HEADERS,
              json={"enabled": True})
```

```json
{
  "use_loop_range": true,
  "loop_in_point": 1010,
  "loop_out_point": 1050
}
```

---

## 5. Loading Media

### POST /api/media/add

Add one or more media files, directories, or image sequence patterns to
xSTUDIO. The media is placed into a named playlist (default: `"Remote API"`).

| Field | Type | Required | Description |
|---|---|---|---|
| `path` | string | one of path/paths | Single file, directory, or pattern |
| `paths` | string[] | one of path/paths | Multiple paths in one request |
| `playlist` | string | no | Target playlist name (default: `"Remote API"`) |

### Add a Single File

```bash
curl -s -X POST \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"path": "L:/tdm/shots/fw/9119/comp/images/FW9119_comp_v001.exr"}' \
  http://localhost:45678/api/media/add
```

```python
requests.post(f"{BASE}/api/media/add",
              headers=HEADERS,
              json={"path": "L:/tdm/shots/fw/9119/comp/images/FW9119_comp_v001.exr"})
```

### Add a Directory of EXR Sequences

Point at a directory and xSTUDIO will detect the sequences inside it.

```bash
curl -s -X POST \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"path": "L:/tdm/shots/fw/9119/comp/images/FW9119_comp_v001/exr"}' \
  http://localhost:45678/api/media/add
```

### Add Multiple Paths at Once

```bash
curl -s -X POST \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "paths": [
      "L:/tdm/shots/fw/9119/comp/images/FW9119_comp_v001/exr",
      "L:/tdm/shots/fw/9119/comp/images/FW9119_comp_v002/exr"
    ],
    "playlist": "Comp Review"
  }' \
  http://localhost:45678/api/media/add
```

```python
requests.post(f"{BASE}/api/media/add",
              headers=HEADERS,
              json={
                  "paths": [
                      "L:/tdm/shots/fw/9119/comp/images/FW9119_comp_v001/exr",
                      "L:/tdm/shots/fw/9119/comp/images/FW9119_comp_v002/exr",
                  ],
                  "playlist": "Comp Review",
              })
```

### Using printf Patterns

For explicit frame ranges, use `%04d` style patterns with a `=start-end`
suffix:

```bash
curl -s -X POST \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"path": "L:/tdm/shots/fw/9119/comp/images/FW9119_comp_v001.%04d.exr=1000-1080"}' \
  http://localhost:45678/api/media/add
```

The API also recognizes `####` hash patterns and `{frame:04d}` Python-style
format strings.

### Response

All variations return the same response shape:

```json
{
  "loaded": [
    {"name": "FW9119_comp_v001", "uuid": "e5f6a7b8-..."},
    {"name": "FW9119_comp_v002", "uuid": "c3d4e5f6-..."}
  ],
  "count": 2,
  "playlist": "Comp Review"
}
```

If a path is rejected by security policy, it appears in the `loaded` array
with an error:

```json
{"error": "Path blocked by policy", "path": "//server/share/file.exr"}
```

---

## 6. Managing Playlists

### Create a New Playlist

```bash
curl -s -X POST \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "Lighting Review"}' \
  http://localhost:45678/api/playlist/create
```

```python
r = requests.post(f"{BASE}/api/playlist/create",
                  headers=HEADERS,
                  json={"name": "Lighting Review"})
print(r.json())
```

```json
{
  "name": "Lighting Review",
  "uuid": "f7g8h9i0-..."
}
```

### Switch Viewport to a Playlist

Look up by name or UUID. This changes what is displayed in the xSTUDIO
viewport.

```bash
# By name
curl -s -X POST \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "Lighting Review"}' \
  http://localhost:45678/api/playlist/view

# By UUID
curl -s -X POST \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"uuid": "f7g8h9i0-..."}' \
  http://localhost:45678/api/playlist/view
```

```python
requests.post(f"{BASE}/api/playlist/view",
              headers=HEADERS,
              json={"name": "Lighting Review"})
```

```json
{
  "viewed": {
    "name": "Lighting Review",
    "uuid": "f7g8h9i0-..."
  }
}
```

### Select Specific Media for Playback/Comparison

To compare specific items, select them by UUID. First get the UUIDs from
`GET /api/playlists` or `GET /api/media`, then pass them to the select
endpoint.

```bash
curl -s -X POST \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"uuids": ["e5f6a7b8-...", "c3d4e5f6-..."]}' \
  http://localhost:45678/api/playlist/select
```

```python
# Get all media UUIDs
r = requests.get(f"{BASE}/api/media", headers=HEADERS)
uuids = [m["uuid"] for m in r.json()["media"][:2]]

# Select first two for A/B comparison
requests.post(f"{BASE}/api/playlist/select",
              headers=HEADERS,
              json={"uuids": uuids})

requests.post(f"{BASE}/api/playhead/compare",
              headers=HEADERS,
              json={"mode": "A/B"})
```

```json
{"selected": 2}
```

### List All Playlists with Media Details

```bash
curl -s -H "X-API-Key: $KEY" http://localhost:45678/api/playlists
```

```json
{
  "playlists": [
    {
      "name": "Comp Review",
      "uuid": "a1b2c3d4-...",
      "media_count": 3,
      "media": [
        {
          "name": "FW9119_comp_v001",
          "uuid": "e5f6a7b8-...",
          "is_online": true,
          "flag_colour": "",
          "flag_text": ""
        }
      ]
    }
  ]
}
```

### List All Media Across All Playlists

```bash
curl -s -H "X-API-Key: $KEY" http://localhost:45678/api/media
```

```json
{
  "media": [
    {
      "name": "FW9119_comp_v001",
      "uuid": "e5f6a7b8-...",
      "playlist": "Comp Review",
      "is_online": true,
      "flag_colour": "",
      "flag_text": ""
    }
  ]
}
```

---

## 7. Real-Time Events (SSE)

The `GET /api/events` endpoint opens a Server-Sent Events stream that pushes
state updates at approximately 4 Hz. Only changed states are sent -- if nothing
changes, no data is pushed.

The stream times out after 5 minutes and sends a `timeout` event. Clients
should reconnect automatically.

### Event Format

Each event is a JSON object on a `data:` line:

```
data: {"timestamp": 1710000000.0, "viewed_container": {"name": "Comp Review", "uuid": "a1b2c3d4-..."}, "playhead": {"playing": true, "position": 1035, "compare_mode": "Off", "media_frame": 35}}
```

The `playhead` object includes `playing`, `position`, `compare_mode`, and
`media_frame` when available.

The timeout event looks like:

```
event: timeout
data: {"reconnect": true}
```

### curl

```bash
curl -s -N -H "X-API-Key: $KEY" http://localhost:45678/api/events
```

The `-N` flag disables output buffering so events print as they arrive.

### Python

```python
import requests

with requests.get(f"{BASE}/api/events",
                  headers=HEADERS,
                  stream=True) as r:
    for line in r.iter_lines(decode_unicode=True):
        if line.startswith("data: "):
            payload = line[6:]
            state = json.loads(payload)
            frame = state.get("playhead", {}).get("position")
            if frame is not None:
                print(f"Frame: {frame}")
```

### JavaScript (EventSource)

The built-in `EventSource` API does not support custom headers. Use a library
like `eventsource` (npm) or pass the key as a query parameter if you add
support for that. Alternatively, use `fetch` with a readable stream:

```javascript
const resp = await fetch("http://localhost:45678/api/events", {
  headers: { "X-API-Key": API_KEY }
});

const reader = resp.body.getReader();
const decoder = new TextDecoder();
let buffer = "";

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });

  const lines = buffer.split("\n");
  buffer = lines.pop();

  for (const line of lines) {
    if (line.startsWith("data: ")) {
      const state = JSON.parse(line.slice(6));
      console.log("Frame:", state.playhead?.position);
    }
  }
}
```

---

## 8. Multi-Instance Sync (Preview)

Two xSTUDIO instances can be loosely synchronized by subscribing to events from
one and forwarding playback commands to the other. This is useful for comparing
work across two monitors or syncing a review lead's viewport with an artist's.

The pattern: read the SSE stream from instance A, detect state changes, and
POST matching commands to instance B.

```python
import json
import requests

INSTANCE_A = "http://localhost:45678"
INSTANCE_B = "http://localhost:45679"
KEY_A = "key-for-instance-a"
KEY_B = "key-for-instance-b"

last_position = None

with requests.get(f"{INSTANCE_A}/api/events",
                  headers={"X-API-Key": KEY_A},
                  stream=True) as stream:
    for line in stream.iter_lines(decode_unicode=True):
        if not line.startswith("data: "):
            continue

        state = json.loads(line[6:])
        ph = state.get("playhead", {})
        position = ph.get("position")

        # Forward seek commands when the frame changes
        if position is not None and position != last_position:
            requests.post(
                f"{INSTANCE_B}/api/playhead/seek",
                headers={"X-API-Key": KEY_B},
                json={"frame": position},
            )
            last_position = position
```

This is a simplified example. A production version would also sync play/pause
state, handle reconnects on timeout, and add error handling.

---

## 9. Configuration

The plugin reads `config.json` from the same directory as `server.py`:

```
portable/share/xstudio/plugin-python/remote_api/config.json
```

```json
{
    "port": 45678,
    "bind_address": "127.0.0.1",
    "api_key": "",
    "cors_origins": [],
    "allowed_roots": []
}
```

### Options

| Field | Default | Description |
|---|---|---|
| `port` | `45678` | TCP port the API listens on |
| `bind_address` | `"127.0.0.1"` | Network interface to bind. `127.0.0.1` restricts access to the local machine. Change to `0.0.0.0` to allow network access (not recommended without a firewall). |
| `api_key` | `""` (auto-generate) | Set a fixed API key. Leave empty to auto-generate one on first launch. |
| `cors_origins` | `[]` (CORS disabled) | List of allowed web origins, e.g. `["http://localhost:3000"]`. Only these origins will receive CORS headers. |
| `allowed_roots` | `[]` (any local path) | Restrict `POST /api/media/add` to paths under these directories. UNC paths (`\\server\share`) are always blocked. |

### Changing the Port

Edit `config.json` and restart xSTUDIO:

```json
{
    "port": 9090
}
```

All API requests would then go to `http://localhost:9090/api/...`.

### Setting Up Allowed Roots

To restrict which directories the API can load media from:

```json
{
    "allowed_roots": [
        "L:/tdm/shots",
        "L:/tdm/assets",
        "D:/review"
    ]
}
```

Any `POST /api/media/add` request for a path outside these roots receives
a `403` error. Symlinks are resolved before checking, so a symlink pointing
outside the allowed roots will be rejected.

### CORS Configuration

To allow a web dashboard at `http://localhost:3000` to call the API:

```json
{
    "cors_origins": [
        "http://localhost:3000"
    ]
}
```

The API sets `Access-Control-Allow-Origin`, `Access-Control-Allow-Methods`, and
`Access-Control-Allow-Headers` only for origins in this list. Wildcard (`*`) is
not supported.

---

## 10. Troubleshooting

### Cannot connect (connection refused)

Check that xSTUDIO is running and the Remote API plugin is loaded. Verify the
port matches your `config.json`. The default is `45678`.

```bash
curl -v http://localhost:45678/api/status
```

If the port is in use by another process, change it in `config.json` and
restart xSTUDIO.

### 401 Unauthorized

The API key is missing or incorrect. Check:

1. Your request includes the `X-API-Key` header (not `Authorization`)
2. The key matches the contents of
   `portable/share/xstudio/plugin-python/remote_api/.api_key`
3. There are no trailing newlines or spaces in your key variable

```bash
# Print the key file contents to verify
cat portable/share/xstudio/plugin-python/remote_api/.api_key
```

### 403 on media add

The path you are trying to load is outside the configured `allowed_roots`, or
it is a UNC path (`\\server\share\...`). UNC paths are always blocked
regardless of configuration.

To fix, either add the parent directory to `allowed_roots` in `config.json` or
clear the list to allow any local path.

### 404 "No active playhead"

Playback commands require a playlist to be viewed. Load media first or switch
to an existing playlist:

```bash
# View a playlist
curl -s -X POST \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "Comp Review"}' \
  http://localhost:45678/api/playlist/view
```

### SSE stream disconnects after 5 minutes

This is expected. The server closes the SSE connection after 5 minutes and
sends a `timeout` event with `{"reconnect": true}`. Your client should
reconnect automatically when this happens.

### Request body too large (413)

The API enforces a 1 MB limit on request bodies. If you are sending a very
long list of paths, split them across multiple requests.
