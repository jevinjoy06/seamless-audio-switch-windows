# Seamless Audio Switch

Replicate AirPods-style seamless device switching for Bluetooth audio devices on Windows.

## Overview

This project enables automatic, seamless switching of a Bluetooth audio device between multiple Windows source devices (laptops, tablets, desktops) based on user intent detection — no manual reconnection needed.

### How It Works

```
┌─────────────┐     UDP/mDNS      ┌─────────────┐
│  Laptop     │◄──────────────────►│  Desktop    │
│  (App)      │                    │  (App)      │
└──────┬──────┘                    └──────┬──────┘
       │ BLE (control)                    │ BLE (control)
       │ A2DP (audio)                     │ A2DP (audio)
       └──────────┐          ┌────────────┘
                  ▼          ▼
              ┌──────────────────┐
              │  Audio Device    │
              │  (Multipoint)    │
              └──────────────────┘
```

1. **Intent Detection** — Each device runs a service that monitors audio playback (WASAPI), screen state, app usage, and idle time to compute an "intent score"
2. **Coordination Protocol** — Devices broadcast their intent scores over the local network (UDP)
3. **Handoff** — The device with the highest score wins; the current device yields, and the new device connects within ~500ms–1.5s
4. **Link Key Sync** — Bluetooth pairing keys are shared across trusted devices via the Windows Registry so no re-pairing is needed

## Windows Smart Yield

**Auto-pause on handoff** — Replicates the Apple ecosystem experience on Windows. When audio devices switch between devices, the yielding device automatically pauses media playback.

### Supported Scenarios

✅ **iPhone → Windows**: When iPhone takes over AirPods, Windows auto-pauses
✅ **Windows ↔ Windows**: Coordinated handoff with auto-pause
✅ **Manual Disconnect**: Turning off headphones pauses media
⚠️ **Windows → iPhone**: Limited by iOS (Windows connects, but can't make iPhone pause)

### How It Works

1. **Coordinated Yield** (Windows peer wins):
   - Higher-priority device broadcasts intent
   - Current device: Pause media → Disconnect Bluetooth → IDLE
   - New device: Connect Bluetooth → Resume playback

2. **External Takeover** (iPhone or manual):
   - Bluetooth disconnect detected
   - Current device: Pause media → IDLE state

### Key Components

- **MediaController** (`src/coordinator/media.py`) — Sends Win32 `VK_MEDIA_PLAY_PAUSE` key via SendInput API
- **BluetoothManager** (`src/bluetooth/manager.py`) — Background monitoring thread detects disconnects
- **CoordinationProtocol** (`src/coordinator/protocol.py`) — Distinguishes coordinated vs unexpected disconnects

## Project Structure

```
seamless-audio-switch/
├── src/
│   ├── coordinator/       # Device coordination protocol
│   │   ├── __init__.py
│   │   ├── protocol.py    # UDP broadcast & negotiation
│   │   └── state.py       # Device state machine
│   ├── intent/            # Intent detection engine
│   │   ├── __init__.py
│   │   ├── detector.py    # Intent score computation
│   │   └── signals.py     # Windows signal sources (WASAPI, Win32)
│   └── bluetooth/         # Bluetooth management
│       ├── __init__.py
│       ├── manager.py     # Windows BT management (PowerShell + PnP)
│       └── key_sync.py    # Link key sharing (Registry + AES-256-GCM)
├── firmware/
│   └── esp32/             # ESP32 multipoint audio device firmware
├── docs/
│   ├── architecture.md
│   └── protocol-spec.md
├── tests/
├── config.example.yaml
├── requirements.txt
├── LICENSE
└── README.md
```

## Quick Start

### Prerequisites

- Windows 10/11
- Python 3.10+
- A Bluetooth Multipoint audio device (for MVP)

### Installation

```bash
git clone https://github.com/YOUR_USERNAME/seamless-audio-switch.git
cd seamless-audio-switch
pip install -r requirements.txt
cp config.example.yaml config.yaml  # Edit with your settings
```

### Run the Application

```bash
python -m src.main --device AA:BB:CC:DD:EE:FF --name my-laptop --port 5555
```

This starts the full coordination daemon with:
- Bluetooth monitoring for automatic disconnect detection
- Media controller for auto-pause on handoff
- UDP broadcast coordination protocol

Optional arguments:
- `--name`: Device name (defaults to hostname)
- `--port`: UDP port for coordination (default: 5555)
- `--log-level`: Logging verbosity (DEBUG, INFO, WARNING, ERROR)

## Configuration

See `config.example.yaml` for all options. Key settings:

```yaml
device:
  name: "my-laptop"
  id: "auto"

coordination:
  transport: "udp"
  port: 5555
  broadcast_interval: 1.0

intent:
  weights:
    audio_playing: 50
    device_unlocked: 20
    media_app_foreground: 15
    device_picked_up: 10
    interaction_recency: 5

bluetooth:
  target_device: "AA:BB:CC:DD:EE:FF"
  key_sync_enabled: true
  key_sync_encryption: "aes-256-gcm"
```

## Protocol Specification

See [docs/protocol-spec.md](docs/protocol-spec.md) for the full coordination protocol specification.

## Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit changes (`git commit -am 'Add my feature'`)
4. Push (`git push origin feature/my-feature`)
5. Open a Pull Request

## License

MIT License — see [LICENSE](LICENSE) for details.
