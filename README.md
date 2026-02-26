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

### Run the Coordination Daemon

```bash
python -m src.coordinator.protocol --config config.yaml
```

### Run Intent Detection

```bash
python -m src.intent.detector --verbose
```

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
