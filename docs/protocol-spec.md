# Coordination Protocol Specification

**Version:** 1.0  
**Status:** Draft

## Overview

The coordination protocol enables multiple devices on the same network to negotiate which device should hold the active Bluetooth audio connection. It uses a distributed priority auction model where devices continuously broadcast their intent scores and the highest-scoring device wins.

## Transport

### UDP Broadcast (Primary)

- Port: 5555 (configurable)
- Broadcast address: `255.255.255.255` or subnet broadcast
- Message format: JSON over UTF-8
- Broadcast interval: 1 second

### BLE Mesh (Alternative)

- Uses BLE advertisements with manufacturer-specific data
- Company ID: TBD (use 0xFFFF for development)
- Advertisement interval: 500ms
- Range: ~30 meters

## Message Format

```json
{
  "version": 1,
  "device_id": "550e8400-e29b-41d4-a716-446655440000",
  "device_name": "my-laptop",
  "intent_score": 70.0,
  "timestamp": 1708900000.123,
  "audio_state": "playing",
  "connection_state": "connected"
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `version` | int | Protocol version (currently 1) |
| `device_id` | string | UUID identifying this device |
| `device_name` | string | Human-readable device name |
| `intent_score` | float | Composite intent score (0–100) |
| `timestamp` | float | Unix timestamp of this message |
| `audio_state` | string | `"playing"`, `"paused"`, or `"idle"` |
| `connection_state` | string | Current state machine state |

## State Machine

```
IDLE → INTENT_DETECTED → REQUESTING → CONNECTED → YIELDING → IDLE
```

### Transitions

| From | To | Trigger |
|------|----|---------|
| IDLE | INTENT_DETECTED | Local intent score > 0 |
| INTENT_DETECTED | REQUESTING | This device has the highest score |
| INTENT_DETECTED | IDLE | Another device has higher score / intent dropped |
| REQUESTING | CONNECTED | Bluetooth connection established |
| REQUESTING | IDLE | Connection failed or preempted |
| CONNECTED | YIELDING | Peer with higher score detected |
| CONNECTED | IDLE | Audio stopped / manual disconnect |
| YIELDING | IDLE | Bluetooth disconnected |

## Handoff Sequence

```
Time    Device A (connected)         Device B (idle)
─────   ─────────────────────        ─────────────────
t+0     Broadcasting score=20        User starts audio
t+0.5   Broadcasting score=20        Detects intent, score=70
t+1     Receives B's score=70        Broadcasting score=70
t+1.1   score < B → YIELDING         Sees A yielding → REQUESTING
t+1.3   Disconnects A2DP             Waiting for disconnect
t+1.5   IDLE                         Connects A2DP
t+2.0                                CONNECTED, audio streaming
```

## Conflict Resolution

1. **Higher score wins** — Always.
2. **Tie-breaking** — Most recent timestamp wins.
3. **Simultaneous requests** — If two devices enter REQUESTING at the same time, the one with the higher score proceeds; the other backs off with a random delay (100–500ms).
4. **Stale peers** — Devices not heard from in 5 seconds are considered offline and removed.

## Security Considerations

- Messages are broadcast in plaintext on the local network. For sensitive environments, use the BLE transport or add TLS/DTLS.
- Device IDs should not be reused across different trust networks.
- Link key sync uses AES-256-GCM encryption (see `key_sync.py`).
