# Architecture

**Analysis Date:** 2026-02-27

## Pattern Overview

**Overall:** Layered event-driven architecture with coordinated state machines

**Key Characteristics:**
- Multi-device coordination via UDP broadcast protocol
- Decentralized decision-making (no central controller)
- Weighted signal aggregation for intent detection
- Windows-native APIs for system integration (WASAPI, Win32, Registry)
- Async I/O for network coordination, sync operations for Windows APIs
- Clean separation: intent detection → coordination → Bluetooth control

## Layers

**Intent Detection Layer:**
- Purpose: Compute composite "intent score" measuring how much this device wants the audio connection
- Location: `src/intent/` (detector.py, signals.py)
- Contains: Signal sources (AudioPlaybackSignal, ScreenStateSignal, MediaAppFocusSignal, InteractionRecencySignal), weighted score aggregation
- Depends on: Windows system APIs (pycaw, User32, Kernel32)
- Used by: CoordinationProtocol (for updating scores before broadcast)

**Coordination Protocol Layer:**
- Purpose: Negotiate device handoff using distributed intent scores; manage state machine; trigger media control
- Location: `src/coordinator/` (protocol.py, state.py, media.py)
- Contains: CoordinationProtocol (broadcast/listen loops), DeviceStateMachine (IDLE → INTENT_DETECTED → REQUESTING → CONNECTED → YIELDING → IDLE), DeviceMessage/PeerDevice (peer tracking), MediaController (Windows media key injection)
- Depends on: Intent signals (via update_intent), BluetoothManager (via callbacks)
- Used by: Main entry point (src/main.py)

**Bluetooth Control Layer:**
- Purpose: Manage Bluetooth A2DP connection state, read link keys from registry for key sync
- Location: `src/bluetooth/` (manager.py, key_sync.py)
- Contains: BluetoothManager (PowerShell-based connection control, registry reader, connection monitoring thread), BTDevice dataclass, ConnectionState enum
- Depends on: Windows PowerShell, Registry APIs, threading
- Used by: CoordinationProtocol (via callbacks for should_connect/should_disconnect, disconnect monitoring)

**Application Entry Point:**
- Purpose: Wire all components together, handle CLI args, manage async lifecycle
- Location: `src/main.py`
- Contains: Component initialization (BluetoothManager, CoordinationProtocol), signal setup, callback binding, graceful shutdown
- Depends on: All three layers
- Used by: CLI invocation

## Data Flow

**Normal Handoff Sequence:**

1. Device B detects user intent (picks up phone, unlocks screen, audio starts playing)
2. IntentDetector.detect() runs signal sources, computes score
3. CoordinationProtocol.update_intent() transitions to INTENT_DETECTED state
4. Device B broadcasts DeviceMessage with intent_score via UDP
5. Device A (currently connected) receives B's message via _handle_peer_message()
6. Device A calls _evaluate_handoff():
   - Compares own score vs. max peer score
   - If B's score > A's score: triggers _yield_connection()
7. Device A's MediaController.pause() sends VK_MEDIA_PLAY_PAUSE Win32 event
8. Device A calls _on_should_disconnect callback → BluetoothManager.disconnect()
9. Device A transitions to YIELDING state
10. Device B receives confirmation (or timeout) and calls _on_should_connect() → BluetoothManager.connect()
11. BluetoothManager uses PowerShell to enable BT audio device via PnP
12. Device B transitions to CONNECTED state
13. Audio streams on Device B; handoff completes in 500ms–1.5s

**Unexpected Disconnect Handling:**

1. BluetoothManager._monitor_loop() polls is_device_connected() every 1 second
2. Detects connected → disconnected transition
3. Triggers on_disconnect callback registered in CoordinationProtocol
4. CoordinationProtocol._handle_disconnect() checks current state:
   - If YIELDING: expected disconnect, skip pause (already paused), go IDLE
   - If CONNECTED: unexpected disconnect (device physically disconnected or taken over), pause media, go IDLE
   - Includes 2-second debounce to prevent rapid disconnect spam

**State Management:**

- CoordinationProtocol.state_machine tracks the device's connection lifecycle
- DeviceStateMachine enforces valid transitions via TRANSITIONS dict
- Peers dict in CoordinationProtocol tracks remote devices, auto-expires after DEVICE_TIMEOUT (5s)
- MediaController is stateless; BluetoothManager tracks internal connection state via _state enum

## Key Abstractions

**IntentResult:**
- Purpose: Encapsulate intent detection output with score, signal readings, audio state
- Examples: `src/intent/detector.py` line 36–47
- Pattern: Dataclass with has_intent property for threshold checking

**SignalSource:**
- Purpose: Abstract interface for OS signal sources
- Examples: AudioPlaybackSignal, ScreenStateSignal, MediaAppFocusSignal, InteractionRecencySignal in `src/intent/signals.py`
- Pattern: ABC with name() and read() methods; each source returns SignalReading (source name, 0.0–1.0 value, timestamp)

**DeviceMessage:**
- Purpose: JSON-serializable protocol message for UDP broadcast
- Examples: `src/coordinator/protocol.py` line 29–46
- Pattern: Dataclass with to_json()/from_json() for serialization

**PeerDevice:**
- Purpose: Represent a discovered peer with intent score, state, and is_alive timeout property
- Examples: `src/coordinator/protocol.py` line 49–61
- Pattern: Dataclass tracking last_seen timestamp for timeout logic

**DeviceState & DeviceStateMachine:**
- Purpose: Enforce valid connection state transitions
- Examples: `src/coordinator/state.py` TRANSITIONS dict, transition() method
- Pattern: Enum + FSM with validation; history tracking for debugging

## Entry Points

**src/main.py:**
- Location: `src/main.py` (async main() function, lines 28–125)
- Triggers: CLI invocation with --device, --name, --port, --log-level flags
- Responsibilities: Parse args, configure logging, instantiate BluetoothManager and CoordinationProtocol, bind callbacks, start monitoring, run async protocol, handle Ctrl+C shutdown

**CoordinationProtocol.start():**
- Location: `src/coordinator/protocol.py` (async start() method, lines 244–263)
- Triggers: Called by main.py after component setup
- Responsibilities: Create UDP socket, start three concurrent async tasks (_broadcast_loop, _listen_loop, _cleanup_loop)

**BluetoothManager.start_monitoring():**
- Location: `src/bluetooth/manager.py` (start_monitoring() method, lines 272–290)
- Triggers: Called by main.py before protocol.start()
- Responsibilities: Spawn daemon thread running _monitor_loop(), poll connection state every 1s

## Error Handling

**Strategy:** Graceful degradation with logging; failures do not crash

**Patterns:**

- **Signal reading failures** (`src/intent/detector.py` lines 78–87): Try/except around signal.read(), log warning, substitute 0.0 value. Allows detector to continue with partial signals.
- **Bluetooth operations** (`src/bluetooth/manager.py` lines 85–123): Catch subprocess.TimeoutExpired and generic Exception. Log error, return False, set state to DISCONNECTED. No exception propagation.
- **Network message parsing** (`src/coordinator/protocol.py` lines 285–293): Try/except for json.JSONDecodeError and TypeError. Log warning, skip malformed message, continue listening.
- **PowerShell execution** (`src/bluetooth/manager.py`): 15-second timeout on connect, 10-second on disconnect. Timeout caught as subprocess.TimeoutExpired.
- **Registry access** (`src/bluetooth/manager.py` lines 235–270): Check for PermissionError (no admin), log specific guidance, return None gracefully.

## Cross-Cutting Concerns

**Logging:**
- Standard Python logging module
- Logger names follow module hierarchy: `src.bluetooth.manager`, `src.coordinator.protocol`, `src.intent.detector`
- Configured in main.py via logging.basicConfig (format, level, datefmt)
- Debug logs for internal state transitions; Info logs for user-visible actions; Warning/Error for failures

**Validation:**
- Bluetooth address validation: `_format_address()` normalizes MAC address format (line 334–339)
- MAC extraction from PnP instance ID: `_extract_mac_from_instance_id()` validates hex chars (line 342–349)
- Intent score threshold: `IntentResult.has_intent` property checks score > 10.0 (line 45–47)
- Message protocol versioning: DeviceMessage includes version field (line 38)

**Authentication:**
- No per-message auth; relies on local network isolation
- Bluetooth link keys read from Registry for optional key sync (not yet fully integrated)
- CLI args do not include credentials; config.yaml contains placeholder for BT_SYNC_SECRET env var

---

*Architecture analysis: 2026-02-27*
