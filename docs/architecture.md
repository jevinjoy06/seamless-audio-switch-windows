# Architecture

## System Overview

Seamless Audio Switch is composed of three main subsystems that work together to replicate AirPods-style automatic device switching on Windows.

```
┌─────────────────────────────────────────────────────────────┐
│                        Device A (Windows)                    │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────┐  │
│  │   Intent      │  │  Coordinator  │  │   Bluetooth      │  │
│  │   Detector    │─►│  Protocol     │─►│   Manager        │  │
│  │              │  │               │  │                  │  │
│  │  - WASAPI    │  │  - Broadcast  │  │  - PowerShell    │  │
│  │  - User32    │  │  - Negotiate  │  │  - PnP Devices   │  │
│  │  - Win32     │  │  - Handoff    │  │  - Registry Keys │  │
│  └──────────────┘  └───────┬───────┘  └──────────────────┘  │
│                            │                                 │
└────────────────────────────┼─────────────────────────────────┘
                             │ UDP
                             ▼
┌────────────────────────────┼─────────────────────────────────┐
│                        Device B (Windows)                    │
│  ┌──────────────┐  ┌──────┴────────┐  ┌──────────────────┐  │
│  │   Intent      │  │  Coordinator  │  │   Bluetooth      │  │
│  │   Detector    │─►│  Protocol     │─►│   Manager        │  │
│  └──────────────┘  └───────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Subsystems

### 1. Intent Detector (`src/intent/`)

Monitors Windows device signals and computes a composite "intent score" that represents how strongly this device wants the audio connection.

**Signal Sources (all using Win32 APIs):**
- `AudioPlaybackSignal` — WASAPI via pycaw, checks if any app is outputting audio (weight: 50)
- `ScreenStateSignal` — OpenInputDesktop to detect lock state (weight: 20)
- `MediaAppFocusSignal` — GetForegroundWindow + GetWindowText for active media apps (weight: 15)
- `InteractionRecencySignal` — GetLastInputInfo for keyboard/mouse idle time (weight: 5)

### 2. Coordination Protocol (`src/coordinator/`)

Handles device discovery and negotiation over the local network.

**Responsibilities:**
- Broadcast intent scores to all peers (UDP broadcast)
- Track peer devices and their states
- Run the handoff state machine
- Trigger Bluetooth connect/disconnect via callbacks

**State Machine:** `IDLE → INTENT_DETECTED → REQUESTING → CONNECTED → YIELDING → IDLE`

### 3. Bluetooth Manager (`src/bluetooth/`)

Manages the actual Bluetooth connection lifecycle on Windows.

**Components:**
- `BluetoothManager` — Connect/disconnect via PowerShell PnP device commands
- `LinkKeyManager` — Extract and inject Bluetooth pairing keys via the Windows Registry

## Data Flow

1. Intent Detector polls Win32 signal sources every 500ms
2. Computed score is passed to the Coordination Protocol
3. Protocol broadcasts score to peers and evaluates if we should connect or yield
4. If we win the auction, Protocol triggers BluetoothManager.connect()
5. If we lose, Protocol triggers BluetoothManager.disconnect()

## Link Key Sync Flow

```
Device A (paired)                    Device B (not paired)
────────────────                     ─────────────────────
1. Read key from Registry
   (HKLM\...\BTHPORT\...\Keys)
2. Encrypt with AES-256-GCM
3. Send over secure channel ───────► 4. Decrypt key bundle
                                     5. Write key to Registry
                                     6. Restart bthserv service
                                     7. Can now connect without pairing!
```

## ESP32 Firmware (planned)

For custom audio hardware, an ESP32 running both BLE and Classic BT:
- Maintains multipoint ACL links with 2+ devices
- Accepts BLE commands to switch active A2DP source
- Advertises connection state for intent detection
