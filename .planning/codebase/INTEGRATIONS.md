# External Integrations

**Analysis Date:** 2026-02-27

## APIs & External Services

**None** - This application does not integrate with external cloud APIs, web services, or third-party REST endpoints.

## Data Storage

**Databases:**
- None - No SQL or NoSQL database. All state is ephemeral and stored in memory.

**File Storage:**
- Local filesystem only - Configuration loaded from `config.yaml` in project root. No cloud sync.

**Caching:**
- None - No caching layer (Redis, Memcached). State is reconstructed each polling cycle.

## Authentication & Identity

**Auth Provider:**
- Custom - No external auth system. Device identification is via hostname (via `socket.gethostname()`) or explicit `--name` parameter.
- Inter-device trust: Based on local network broadcast (UDP). No authentication protocol between peers.

## Monitoring & Observability

**Error Tracking:**
- None - No external error tracking (Sentry, Rollbar, etc.)

**Logs:**
- Standard Python logging to console (stderr) by default
- Optional file logging: Configurable via `config.yaml` logging.file parameter
- Timestamps and log levels (DEBUG, INFO, WARNING, ERROR) configurable

## CI/CD & Deployment

**Hosting:**
- N/A - This is a desktop/local-network daemon, not a cloud application

**CI Pipeline:**
- None detected - No GitHub Actions, GitLab CI, Jenkins, etc.

## Environment Configuration

**Required env vars:**
- None explicitly required. All configuration is via command-line arguments or `config.yaml`.

**Optional env vars:**
- `BT_SYNC_SECRET` - Shared secret for deriving link key encryption keys (for future use in multi-device sync; currently not fully implemented)

**Secrets location:**
- Windows Registry (HKLM) - Bluetooth pairing keys stored by Windows kernel, read via winreg module
- `config.yaml` - May contain Bluetooth target device MAC address (not a secret per se, but device-specific)
- No `.env` file used

## Webhooks & Callbacks

**Incoming:**
- None - Application does not expose HTTP endpoints

**Outgoing:**
- None - Application does not make REST API calls or send webhooks

## Local Network Communication

**UDP Broadcast (Port 5555, default):**
- **Purpose:** Inter-device coordination protocol
- **Implementation:** `src/coordinator/protocol.py` - CoordinationProtocol class
- **Message format:** JSON serialized DeviceMessage containing:
  - device_id (UUID)
  - device_name (hostname)
  - intent_score (float)
  - timestamp (seconds since epoch)
  - audio_state ("idle", "playing", "paused")
  - connection_state ("connected", "disconnected", "connecting", "yielding")
- **Broadcast interval:** 1.0 second (configurable via `broadcast_interval` in config)
- **Peer timeout:** 5.0 seconds (configurable via `peer_timeout` in config)
- **Protocol security:** No encryption, no authentication. Relies on LAN isolation.

## Windows Registry Access

**Path:** `HKLM\SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Keys`
- **Purpose:** Read Bluetooth link keys for audio device pairing
- **Read access:** `src/bluetooth/manager.py` get_link_key(), `src/bluetooth/key_sync.py` extract_key()
- **Write access:** `src/bluetooth/key_sync.py` inject_key()
- **Requires:** Administrator privileges
- **Encryption in transit:** AES-256-GCM (when keys are synced between devices)

## PowerShell Subprocess Calls

**From:** `src/bluetooth/manager.py`
- **Purpose:** Connect/disconnect Bluetooth audio devices
- **Commands:**
  - `Get-PnpDevice` - Enumerate paired Bluetooth devices
  - `Enable-PnpDevice` - Connect to audio device
  - `Disable-PnpDevice` - Disconnect from audio device
- **Requires:** Administrator privileges
- **Error handling:** Subprocess timeouts (15s for connect, 10s for disconnect, 5s for list, 10s for query)

## Windows WASAPI (via pycaw)

**From:** `src/intent/signals.py` AudioPlaybackSignal
- **Purpose:** Detect active audio playback and measure audio peak levels
- **Implementation:** pycaw.AudioUtilities.GetAllSessions() → IAudioMeterInformation.GetPeakValue()
- **Fallback:** If pycaw unavailable, queries winmm.waveOutGetNumDevs() for device count

## Win32 User Input API

**From:** `src/coordinator/media.py` MediaController
- **Purpose:** Send media control key (VK_MEDIA_PLAY_PAUSE) to pause/resume audio
- **API:** user32.SendInput() with KEYBDINPUT structure
- **Works across:** All media applications (Spotify, Chrome, VLC, Windows Media Player, etc.)

## Inter-Device Link Key Synchronization

**Encryption:** AES-256-GCM (via cryptography library)
- **Key derivation:** PBKDF2-SHA256 from shared secret (100,000 iterations)
- **Format:** Nonce (12 bytes) + ciphertext + GCM tag (16 bytes)
- **Transport:** Currently defined in `src/bluetooth/key_sync.py` but not yet fully integrated into coordination protocol

---

*Integration audit: 2026-02-27*
