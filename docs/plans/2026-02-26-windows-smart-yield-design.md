# Windows Smart Yield - Design Document

**Date:** 2026-02-26
**Status:** Approved
**Feature:** Auto-pause on handoff with cross-platform support

---

## Overview

Implement "Windows Smart Yield" to replicate the Apple ecosystem handoff experience on Windows. When audio devices switch between devices (Windows ↔ Windows or iPhone → Windows), the yielding device automatically pauses media playback.

### Goal

Enable seamless audio handoff with automatic media pause:
- ✅ **iPhone → Windows**: When iPhone takes over AirPods, Windows auto-pauses
- ✅ **Windows ↔ Windows**: Coordinated handoff with auto-pause
- ⚠️ **Windows → iPhone**: Limited by iOS (Windows connects, but can't make iPhone pause)

---

## Architecture Overview

### Three Handoff Scenarios

**1. Windows Peer Wins (Coordinated Handoff)**
- Windows Laptop-2 starts playing → intent score rises
- Windows Laptop-1 sees higher score via UDP broadcast
- Laptop-1: Pause media → Disconnect Bluetooth → IDLE
- Laptop-2: Connect Bluetooth → Play music

**2. iPhone Takes Over (External Handoff)**
- User starts playing on iPhone
- iPhone connects to AirPods (Apple's native handoff)
- Windows detects Bluetooth disconnect
- Windows: Pause media → IDLE state

**3. Manual Disconnect**
- User turns off headphones or manually disconnects
- Windows detects disconnect
- Windows: Pause media → IDLE state

### Component Architecture

```
┌─────────────────────────────────────────────────┐
│         CoordinationProtocol                     │
│  - Tracks Bluetooth state                       │
│  - Decides: coordinated vs external disconnect  │
│  - Triggers MediaController when needed         │
└─────────┬───────────────────────┬───────────────┘
          │                       │
          ▼                       ▼
┌─────────────────┐     ┌──────────────────────┐
│ MediaController │     │  BluetoothManager    │
│ - Pause media   │     │  - Monitor state     │
│ - Media keys    │     │  - Connect/disconnect│
└─────────────────┘     └──────────────────────┘
```

---

## Components Design

### New Component: MediaController

**File:** `src/coordinator/media.py`

```python
class MediaController:
    """Handles media playback control via Windows media keys."""

    def pause() -> bool:
        """
        Send VK_MEDIA_PLAY_PAUSE key to pause media.
        Uses Win32 SendInput API.
        Works with: Spotify, Chrome, VLC, Windows Media Player, etc.
        Returns True if key was sent successfully.
        """
```

**Implementation:**
- Use `ctypes` to call Win32 `SendInput` API
- Send `VK_MEDIA_PLAY_PAUSE` (0xB3) keycode
- Simple, universal compatibility with media apps

---

### Updated: BluetoothManager

**File:** `src/bluetooth/manager.py`

**New functionality:**
- Background monitoring thread that polls Bluetooth connection state (every 1 second)
- Callback mechanism to notify coordinator when disconnect happens
- `is_connected()` method using PowerShell device status check

```python
class BluetoothManager:
    def __init__(self, target_device: str, on_disconnect_callback: Callable):
        self.target_device = target_device
        self._on_disconnect = on_disconnect_callback
        self._connection_state = "disconnected"
        self._monitor_thread = None

    def start_monitoring(self):
        """Start background thread watching Bluetooth connection."""

    def is_connected() -> bool:
        """Check current connection state via PowerShell."""
```

---

### Updated: CoordinationProtocol

**File:** `src/coordinator/protocol.py`

**New logic:**

```python
class CoordinationProtocol:
    def __init__(self, ..., bluetooth_manager: BluetoothManager):
        self.bt_manager = bluetooth_manager
        self.media_controller = MediaController()

        # Register for unexpected disconnects
        bluetooth_manager.on_disconnect_callback = self._handle_disconnect

    def _yield_connection(self):
        """Coordinated yield to Windows peer."""
        self.state_machine.transition(DeviceState.YIELDING)
        logger.info("Yielding to peer device")

        # PAUSE, THEN DISCONNECT (in order)
        self.media_controller.pause()
        self._on_should_disconnect()  # Calls BluetoothManager.disconnect()

    def _handle_disconnect(self):
        """Called when Bluetooth disconnects unexpectedly."""
        if self.state_machine.state == DeviceState.YIELDING:
            # Expected disconnect from coordinated yield - already paused
            return

        # ANY other disconnect → pause media
        logger.info("Bluetooth disconnected - pausing media")
        self.media_controller.pause()
        self.state_machine.transition(DeviceState.IDLE)
```

**Key insight:** Distinguish between coordinated yield (already handled) vs unexpected disconnect (iPhone or manual).

---

## Data Flow & State Transitions

### Scenario 1: Windows Peer Wins

```
Time    This Device (Laptop-1)              Peer Device (Laptop-2)
────    ──────────────────────────          ───────────────────────
t+0     CONNECTED, playing music            IDLE, user starts music
        Intent score: 50                    Intent score: 70

t+1     Receives peer broadcast score=70    Broadcasting score=70
        score > 50 → _evaluate_handoff()

t+1.1   _yield_connection() called
        State: CONNECTED → YIELDING

t+1.2   MediaController.pause()             Waiting...
        [Media paused ✓]

t+1.3   BluetoothManager.disconnect()       Sees YIELDING → REQUESTING

t+1.5   State: YIELDING → IDLE              Connects Bluetooth

t+2.0                                       CONNECTED, music playing
```

### Scenario 2: iPhone Takes Over

```
Time    Windows Device                      iPhone
────    ──────────────────────             ──────────────────────
t+0     CONNECTED, playing music           Idle

t+1                                        User plays music
                                           iPhone connects to AirPods

t+1.2   BluetoothManager detects           AirPods connected
        disconnect event

t+1.3   _handle_disconnect() called
        State: CONNECTED (unexpected!)

t+1.4   MediaController.pause()
        [Media paused ✓]

t+1.5   State: CONNECTED → IDLE            Music playing on iPhone
        Log: "Bluetooth disconnected - pausing media"
```

### Scenario 3: Manual Disconnect

```
Time    Windows Device                     User Action
────    ──────────────────────            ──────────────────────
t+0     CONNECTED, playing music          Turns off headphones

t+1     BluetoothManager detects          Headphones offline
        disconnect event

t+2     _handle_disconnect() called

t+3     MediaController.pause()
        [Media paused ✓]
        State: CONNECTED → IDLE
```

---

## Error Handling & Edge Cases

### 1. Media Pause Fails
- **Issue:** `SendInput` fails (permissions, Win32 error)
- **Solution:** Log error, continue with disconnect anyway
- **Rationale:** Better to disconnect cleanly than block handoff

### 2. Bluetooth State Monitoring Fails
- **Issue:** PowerShell timeout, device unpaired
- **Solution:** Assume disconnected, trigger pause, log error
- **Rationale:** Safe default - treat unknown as "not connected"

### 3. Rapid Connect/Disconnect Loops
- **Issue:** Flaky Bluetooth, repeated disconnect events
- **Solution:** Debounce disconnect events (ignore within 2 seconds of last)
- **Implementation:**
  ```python
  self._last_disconnect_time = 0

  def _handle_disconnect(self):
      now = time.time()
      if now - self._last_disconnect_time < 2.0:
          logger.debug("Ignoring rapid disconnect (debounce)")
          return

      self._last_disconnect_time = now
      # ... proceed with pause
  ```

### 4. Both Devices Request Simultaneously
- **Issue:** Windows devices detect intent at same time
- **Solution:** Already handled by existing tie-breaking (score, then timestamp)
- **No changes needed**

### 5. iPhone and Windows Compete Rapidly
- **Issue:** User switches between devices quickly
- **Solution:** Each disconnect triggers pause (correct behavior)
- **Rationale:** Bluetooth handles connection race at hardware level

---

## Testing Strategy

### Manual Testing Scenarios

**Test 1: Windows ↔ Windows Handoff**
- Play on Laptop-1 → Start on Laptop-2
- Verify: Laptop-1 paused ✓, Laptop-2 connected ✓
- Expected logs: `"Yielding to peer device"`

**Test 2: iPhone → Windows**
- Play on Windows → Play on iPhone
- Verify: Windows paused ✓, went to IDLE ✓
- Expected logs: `"Bluetooth disconnected - pausing media"`

**Test 3: Windows → iPhone**
- Play on iPhone → Start on Windows
- Verify: Windows tries to connect
- Note: iPhone won't auto-pause (Apple limitation)

**Test 4: Manual Disconnect**
- Play on Windows → Turn off headphones
- Verify: Windows paused ✓

**Test 5: Rapid Switching (Debounce)**
- Simulate flaky connection
- Verify: Only first disconnect triggers pause

### Unit Tests

```python
# tests/test_media_controller.py
def test_pause_sends_media_key()

# tests/test_coordination_handoff.py
def test_coordinated_yield_pauses_then_disconnects()
def test_unexpected_disconnect_triggers_pause()
def test_yielding_state_disconnect_ignored()
```

### Testing Requirements
- 2+ Windows devices for peer testing
- iPhone for cross-platform testing
- Bluetooth headphones (multipoint-capable preferred)
- Verbose logging enabled

---

## Implementation Notes

### Pause Timing
- **Coordinated yield:** Pause BEFORE disconnect (explicit in code)
- **Unexpected disconnect:** Pause AFTER detection (reactive)

### Cross-Platform Limitations
- **iPhone → Windows:** ✅ Works seamlessly (Windows detects and pauses)
- **Windows → iPhone:** ⚠️ Limited by iOS (can't make iPhone pause without jailbreak/app)
- **Workaround:** Acceptable limitation, matches user expectation

### Future Extensions (Not in Scope)
- Apple-style notification UI (separate feature)
- Auto-resume on reconnect (explicitly rejected by user)
- BLE coordination for better Apple device detection (over-engineering)

---

## Success Criteria

✅ Windows pauses media when iPhone takes AirPods
✅ Windows pauses media when another Windows device wins
✅ Windows pauses media on manual disconnect
✅ Coordinated handoff completes within 1.5 seconds
✅ No double-pause on expected disconnects
✅ Debouncing prevents spam from flaky connections
✅ Unit tests cover all state transitions

---

## Next Steps

1. Create implementation plan (invoke `writing-plans` skill)
2. Implement `MediaController` class
3. Update `BluetoothManager` with monitoring
4. Update `CoordinationProtocol` with pause logic
5. Add unit tests
6. Manual testing with Windows + iPhone
7. Documentation update
