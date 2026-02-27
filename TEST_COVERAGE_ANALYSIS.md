# Test Coverage Analysis: Windows Smart Yield Implementation

**Analysis Date:** 2026-02-26
**Total Test Cases:** 13 across 4 files
**Implementation Files Analyzed:** 6 core modules

---

## Executive Summary

The Windows Smart Yield implementation has foundational test coverage but significant gaps in critical areas. Coverage includes basic unit tests for media control and Bluetooth monitoring, plus integration tests for the main workflow. However, critical edge cases, error scenarios, and advanced protocol features are largely untested.

**Overall Risk Level:** HIGH

Key gaps:
- Network protocol error handling and message validation
- Bluetooth connection edge cases and timing issues
- State machine invariant violations under stress
- Error recovery and cleanup paths
- Intent detector signal failures and fallbacks
- DeviceMessage parsing resilience

---

## CRITICAL Severity Issues

### 1. CoordinationProtocol Network Layer (Untested)
**Files:** `src/coordinator/protocol.py` (async networking code)
**Lines:** 244-304 (broadcast_loop, listen_loop, cleanup_loop)

**What's covered:**
- Message serialization/deserialization (basic happy path in test_core.py)
- Peer state transitions (test_core.py)

**What's NOT covered:**
- Socket creation failures
- Broadcast failures (sendto exceptions)
- Malformed JSON message handling beyond JSONDecodeError
- Invalid DeviceMessage fields (missing/wrong types)
- Network timeouts and reconnection logic
- Cleanup loop behavior with stale peers
- Resource cleanup if tasks are cancelled

**Risk:** Network-level failures will crash the protocol loop. No graceful degradation.

**Example scenarios missing:**
```python
# Socket binding failures
# Broadcast to unreachable address
# Receive oversized packet (>4096 bytes)
# Corrupted binary data in UDP packet
# Peer update spam causing memory leaks
# Task cancellation during cleanup
```

---

### 2. BluetoothManager Connection Edge Cases (Severely Undertested)
**Files:** `src/bluetooth/manager.py`
**Coverage:** Only disconnect detection tested

**What's covered:**
- Disconnect detection trigger (4 tests)
- Basic threading (start/stop monitoring)

**What's NOT covered:**

#### 2a. Connect Operation Failure Modes
- PowerShell execution failures
- Device not found scenarios
- Connection timeout handling (15s timeout)
- Timeout retry logic
- Race conditions between connect attempts
- State machine corruption if connect fails mid-operation

**Missing tests:**
```python
# Device not found → DEVICE_NOT_FOUND in stdout
# PowerShell timeout → subprocess.TimeoutExpired
# Exception during connect → state still DISCONNECTED?
# Rapid connect/disconnect/connect sequences
# Connect while already connecting
```

#### 2b. Registry/LinkKey Operations
- Registry access denied (PermissionError)
- Registry key not found
- Device address formatting edge cases
- Link key extraction failures

**Missing tests:**
```python
# get_link_key with admin access denied
# Device address "AA-BB-CC-DD-EE-FF" format
# Device address without colons "AABBCCDDEEFF"
# Malformed MAC addresses
# Registry path enumeration failures
```

#### 2c. List Paired Devices Parsing
- PowerShell output with unusual characters
- Devices without FriendlyName
- Unexpected status values
- Empty output handling

**Missing tests:**
```python
# Device name with pipes: "Audio Device|Status"
# Status value not "OK" or "Error"
# Instance ID without MAC address pattern
# Completely empty device list output
```

#### 2d. Disconnect Operation
- Disconnect while connecting
- Disconnect failures (only return value tested, not error recovery)
- Device already disconnected
- Unexpected PowerShell errors

---

### 3. MediaController Error Handling (Incomplete)
**Files:** `src/coordinator/media.py`

**What's covered:**
- SendInput success (return=2)
- SendInput failure (return=0)

**What's NOT covered:**
- SendInput returning 1 (partial success)
- Exception types during INPUT structure creation
- ctypes.windll.user32 not available
- Invalid key codes (what if VK_MEDIA_PLAY_PAUSE is wrong?)
- Keyboard hook installed that blocks SendInput
- Empty events array

**Missing tests:**
```python
# result = 1 (partial success, edge case)
# ctypes structure creation raises MemoryError
# user32.SendInput raises AccessDenied
# Exception in KEYBDINPUT initialization
```

---

### 4. DeviceStateMachine Invalid Transitions Under Concurrency
**Files:** `src/coordinator/state.py`

**What's covered:**
- Valid transitions
- Invalid transitions (rejected)
- State properties

**What's NOT covered:**
- Concurrent transition attempts from multiple threads
- Race condition: check current state + transition in 2 steps
- History tracking under rapid transitions
- State leakage if transition fails but logs are lost

**Missing tests:**
```python
# Thread A: transition(REQUESTING) while Thread B: transition(IDLE)
# History length grows unbounded in long-running app
# Invalid transition silently fails (no exception raised, just logged)
```

---

## HIGH Severity Issues

### 5. CoordinationProtocol State Handoff Logic (Incomplete)
**Files:** `src/coordinator/protocol.py` (lines 135-159)

**What's covered:**
- Yield when peer score is higher
- Don't yield when peer is already yielded

**What's NOT covered:**

#### 5a. Tie-Breaking Logic
- Line 159: `else: pass  # Tie — most recent timestamp wins`
- **NOT IMPLEMENTED** — what actually happens on tie?
- Does device request or stay idle?

**Missing tests:**
```python
# Device A score=50, timestamp=100
# Device B score=50, timestamp=99
# Who wins? Who connects? Who yields?
```

#### 5b. Stale Peer Handling During Handoff
- Peer goes offline while this device is YIELDING
- Should this device reconnect or stay idle?
- Current code doesn't handle this scenario

**Missing tests:**
```python
# Device connected and YIELDING to peer-123
# peer-123 expires (is_alive=False)
# Does device reconnect?
```

#### 5c. Multiple Peers with Different Scores
- What if 3+ peers exist?
- Should device yield to highest or just any higher?
- Score comparison: exact equality vs. floating-point epsilon

**Missing tests:**
```python
# Peers: A=50.0, B=50.0, C=49.9
# Current device=50.0
# Multiple score comparisons
```

#### 5d. Callback Exceptions
- If on_should_connect or on_should_disconnect raises exception
- Does protocol continue or crash?

**Missing tests:**
```python
# on_should_disconnect raises RuntimeError
# Protocol state = ?
```

---

### 6. Intent Detector Signal Failures (Not Tested)
**Files:** `src/intent/detector.py`

**What's covered:**
- Score computation with mock signals
- Weight application

**What's NOT covered:**
- Real signal source exception handling
- Partial signal failure (some signals work, some fail)
- All signals fail → what's the final score?
- Signal timeout/deadlock scenarios

**Missing tests:**
```python
# AudioPlaybackSignal raises PermissionError
# ScreenStateSignal.read() hangs indefinitely
# MediaAppFocusSignal returns non-0.0-1.0 value
# All signals fail → detector returns fallback?
```

---

### 7. Signal Sources Exception Paths (Untested)
**Files:** `src/intent/signals.py`

#### 7a. AudioPlaybackSignal
- pycaw import fails (line 87-90) → tested with fallback
- GetAllSessions returns None or empty
- QueryInterface raises exception for each session
- peak > 0.01 threshold boundary

**Missing tests:**
```python
# pycaw installed but GetAllSessions() fails
# Peak = 0.01 exactly (threshold boundary)
# Peak = 0.009 (below threshold)
# Exception during meter.GetPeakValue()
```

#### 7b. MediaAppFocusSignal
- _get_process_name returns non-string
- GetForegroundWindow returns None
- GetWindowTextLengthW returns 0 but GetWindowTextW fails
- Buffer overflow scenarios

**Missing tests:**
```python
# GetForegroundWindow returns invalid handle (0)
# GetWindowTextLengthW returns large value (>10000)
# Process lookup hangs (GetModuleBaseNameW timeout)
# Window title with emoji/unicode characters
```

#### 7c. InteractionRecencySignal
- GetLastInputInfo returns False
- Idle time calculation overflows
- Tick count wraps around (every 49.7 days on Windows)

**Missing tests:**
```python
# GetLastInputInfo returns False
# idle_ms is negative (tick count wrapped)
# idle_sec = -1000.0 (how does max(0.0, ...) behave?)
```

---

### 8. BluetoothManager Monitoring Thread Lifecycle (Incomplete)
**Files:** `src/bluetooth/manager.py` (lines 272-311)

**What's covered:**
- Thread creation and starting
- Basic stop logic

**What's NOT covered:**
- Thread still running after stop_monitoring called
- join() timeout exceeded (thread hangs)
- Exception during _monitor_loop kills thread silently
- Exception in _on_disconnect callback
- _check_connection_state exception handling
- Double start_monitoring call (idempotence)
- Callback exception doesn't propagate

**Missing tests:**
```python
# _on_disconnect raises exception → monitoring continues?
# is_device_connected hangs → monitoring thread blocked
# Exception in _check_connection_state → thread dies?
# Thread survives but _monitoring=False (state leak)
```

---

## HIGH Severity Issues (Integration/Main)

### 9. Main Entry Point Error Handling (Virtually Untested)
**Files:** `src/main.py`

**What's covered:**
- No tests exist for main.py

**What's NOT covered:**
- Invalid device address format
- Missing --device argument
- BluetoothManager.connect() fails → protocol continues?
- Coordination protocol crashes → graceful shutdown?
- KeyboardInterrupt handling during startup
- Logging configuration errors
- All callbacks properly wired?

**Missing tests:**
```python
# main.py --device "INVALID_ADDRESS"
# main.py --device "AA:BB:CC:DD:EE:FF" (device not found)
# Protocol crash during startup → finally block runs?
# Callbacks fire in correct order?
```

---

## MEDIUM Severity Issues

### 10. Protocol Message Validation (Missing)
**Files:** `src/coordinator/protocol.py` (DeviceMessage)

**What's covered:**
- Serialization roundtrip (test_core.py)

**What's NOT covered:**
- Empty device_id
- None values for required fields
- Negative intent_score
- Timestamp in future or past
- Audio_state with invalid values
- Oversized fields causing buffer issues

**Missing tests:**
```python
# DeviceMessage(device_id="", ...)
# DeviceMessage(intent_score=-50.0, ...)
# DeviceMessage(timestamp=9999999999999.0, ...)
# from_json with missing required field
# from_json with extra unknown fields
```

---

### 11. Pause and Disconnect Ordering (Partially Tested)
**Files:** `src/coordinator/protocol.py` (lines 169-186)

**What's covered:**
- Pause called before disconnect (test_coordination_pause.py:39-61)
- Pause failure doesn't stop disconnect

**What's NOT covered:**
- What if disconnect callback raises exception after pause?
- What if pause completes but disconnect takes too long?
- Media resume on disconnect failure?
- Pause state synchronization with actual media application

**Missing tests:**
```python
# on_should_disconnect raises exception after pause=True
# Pause returns True but disconnect takes 5+ seconds
# Bluetooth disconnects WHILE pause() is executing
```

---

### 12. DeviceMessage Version Handling (Not Tested)
**Files:** `src/coordinator/protocol.py` (line 38)

**What's covered:**
- Default version=1 assignment

**What's NOT covered:**
- Receiving message with version=2 (future compatibility)
- Receiving message with version=0 (past compatibility)
- Version mismatch handling
- from_json silently ignores version field

**Missing tests:**
```python
# Peer device broadcasts version=2 message
# Current device version=1, peer version=2
# Fallback/upgrade logic?
```

---

### 13. Debounce Logic Edge Cases (Partially Tested)
**Files:** `src/coordinator/protocol.py` (lines 203-207)

**What's covered:**
- Debounce at 2-second interval (test_coordination_pause.py:105-139)

**What's NOT covered:**
- System clock goes backward (time.time() regression)
- Rapid disconnect within sub-millisecond window
- Multiple disconnects in flight (async race)
- Debounce timer longer than actual disconnect duration

**Missing tests:**
```python
# time.time() returns 1000.0
# Then next call returns 999.5 (backward)
# Debounce comparison: 999.5 - 1000.0 < 2.0? (negative!)
# Two concurrent _handle_disconnect calls
```

---

## MEDIUM Severity Issues (Signals)

### 14. Signal Source Exception Resilience (Incomplete)
**Files:** `src/intent/detector.py` (lines 78-87)

**What's covered:**
- Signal exception caught (line 85)
- Returns 0.0 as fallback

**What's NOT covered:**
- Signal.read() timeout or deadlock
- Signal exception type verification (catches Exception)
- Partial signal failure (some working, some dead)
- Signal state after exception (is it recoverable?)
- Memory leak from repeated exceptions

**Missing tests:**
```python
# 1 of 4 signals raises OutOfMemoryError
# Signal exception type: RuntimeError vs. OSError
# After signal fails once, does it recover?
# Exception spam in logs (10K exceptions/sec)
```

---

## LOW Severity Issues

### 15. Logging and Observability (Inconsistent)
**Files:** All modules

**What's covered:**
- Most major operations logged

**What's NOT covered:**
- Log level verification in tests
- WARNING vs. ERROR discrimination
- DEBUG logs present in critical paths
- Exception stack traces in error logs
- Performance metrics (elapsed time, latency)

**Missing tests:**
```python
# Verify WARNING logged on pause failure
# Verify DEBUG logged on successful state transition
# No INFO spam during normal operation
```

---

### 16. Resource Cleanup (Partially Tested)
**Files:** `src/bluetooth/manager.py`, `src/coordinator/protocol.py`

**What's covered:**
- stop_monitoring() basic cleanup
- protocol.stop() socket closing

**What's NOT covered:**
- Socket/thread cleanup if exception occurs
- Memory cleanup from peer dict (can grow unbounded)
- Callback references holding onto objects
- Proper daemon thread behavior

**Missing tests:**
```python
# Protocol crashes → socket properly closed?
# Peer dict grows to 1000 entries → memory usage?
# Thread not marked daemon → test hangs?
```

---

### 17. Configuration/Constants (Not Validated)
**Files:** `src/coordinator/protocol.py` (lines 22-26)

**What's tested:** Nothing

**What's NOT covered:**
- BROADCAST_INTERVAL = 1.0 → can be 0 or negative
- DEVICE_TIMEOUT = 5.0 → can be < BROADCAST_INTERVAL
- DEFAULT_PORT = 5555 → can be outside valid range
- No validation of constants on startup

**Missing tests:**
```python
# CoordinationProtocol(port=-1)
# CoordinationProtocol(port=99999)
# BROADCAST_INTERVAL > DEVICE_TIMEOUT (peers expire before update)
```

---

## Coverage Summary by Module

| Module | File | Lines | Tests | Coverage | Risk |
|--------|------|-------|-------|----------|------|
| Bluetooth Manager | `src/bluetooth/manager.py` | 350 | 4 | 11% | CRITICAL |
| Coordination Protocol | `src/coordinator/protocol.py` | 332 | 5 | 15% | CRITICAL |
| Media Controller | `src/coordinator/media.py` | 103 | 2 | 19% | CRITICAL |
| State Machine | `src/coordinator/state.py` | 71 | 7 | 40% | HIGH |
| Intent Detector | `src/intent/detector.py` | 142 | 4 | 28% | HIGH |
| Signal Sources | `src/intent/signals.py` | 265 | 0 | 0% | CRITICAL |
| Main | `src/main.py` | 126 | 0 | 0% | HIGH |
| **TOTAL** | | **1389** | **22** | **1.6%** | **CRITICAL** |

---

## Recommended Test Implementation Priority

### Phase 1: CRITICAL (Block Production)
1. **Network Protocol Error Handling** (CoordinationProtocol)
   - Socket creation/binding failures
   - Malformed message handling
   - Resource cleanup on exception
   - Estimated: 15-20 test cases

2. **Bluetooth Connection Edge Cases** (BluetoothManager)
   - PowerShell execution failures
   - Registry/link key edge cases
   - Connection timeout and retry
   - Monitoring thread robustness
   - Estimated: 20-25 test cases

3. **MediaController Exception Handling** (MediaController)
   - All exception paths
   - ctypes failures
   - Partial success scenarios
   - Estimated: 8-10 test cases

### Phase 2: HIGH (Before 1.0 Release)
4. **Protocol Handoff Logic** (CoordinationProtocol)
   - Tie-breaking implementation
   - Stale peer handling
   - Multiple peer scenarios
   - Callback exception handling
   - Estimated: 12-15 test cases

5. **Signal Source Failures** (IntentDetector + Signals)
   - Per-signal exception paths
   - Partial failures
   - Threshold boundaries
   - Estimated: 20-25 test cases

6. **Main Entry Point** (main.py)
   - Argument validation
   - Error handling during startup
   - Callback wiring verification
   - Graceful shutdown
   - Estimated: 10-12 test cases

### Phase 3: MEDIUM (Polish)
7. **Message Validation** (DeviceMessage)
   - Field validation
   - Version compatibility
   - Oversized data
   - Estimated: 10-12 test cases

8. **Concurrency & Timing**
   - Thread safety
   - Race conditions
   - Timing assumptions
   - Estimated: 15-20 test cases

---

## Testing Strategy Recommendations

### Approach
1. **Mocking Strategy**: Continue mocking Win32 APIs (user32, kernel32) to avoid environment dependencies
2. **Async Testing**: Use pytest-asyncio for CoordinationProtocol async tests
3. **Threading**: Use ThreadPoolExecutor to run BluetoothManager tests concurrently
4. **Time Mocking**: Mock time.time() for debounce and timeout tests

### Example Test Structure
```python
# For network errors
@pytest.fixture
def broken_socket():
    with patch('socket.socket') as mock_sock:
        mock_sock.side_effect = OSError("Address already in use")
        yield mock_sock

# For Bluetooth failures
@pytest.fixture
def bluetooth_timeout():
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired("powershell", 15)
        yield mock_run

# For signal failures
@pytest.fixture
def broken_signal():
    signal = MockSignal("audio_playing", 0.0)
    signal.read = MagicMock(side_effect=RuntimeError("WASAPI error"))
    return signal
```

### Continuous Testing
- Run full test suite on every commit
- Add coverage gates (minimum 80% for new code)
- Track coverage trends in CI/CD

---

## Files Requiring Immediate Test Coverage

| Severity | File | Gap | Tests Needed |
|----------|------|-----|--------------|
| CRITICAL | `src/bluetooth/manager.py` | Connect/disconnect/registry | 25+ |
| CRITICAL | `src/coordinator/protocol.py` | Network/async/handoff | 30+ |
| CRITICAL | `src/coordinator/media.py` | Exception handling | 10+ |
| CRITICAL | `src/intent/signals.py` | All signal sources | 25+ |
| HIGH | `src/main.py` | All paths | 15+ |
| HIGH | `src/intent/detector.py` | Signal failures | 15+ |
| MEDIUM | `src/coordinator/state.py` | Concurrency | 10+ |

**Total Tests Needed:** 130+ additional test cases
**Estimated Implementation Time:** 3-4 weeks (with experienced test engineer)

---

## Appendix: Example Critical Test Cases

### Example 1: BluetoothManager PowerShell Timeout
```python
def test_connect_timeout_handling():
    """Test that connection timeout is handled gracefully."""
    manager = BluetoothManager(target_address="AA:BB:CC:DD:EE:FF")

    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired("powershell", 15)

        result = manager.connect()

        assert result is False
        assert manager.state == ConnectionState.DISCONNECTED
        # Verify state wasn't corrupted to CONNECTING
```

### Example 2: CoordinationProtocol Malformed Message
```python
@pytest.mark.asyncio
async def test_listen_loop_corrupted_json():
    """Test that corrupted JSON is gracefully skipped."""
    protocol = CoordinationProtocol(device_name="test")

    with patch.object(protocol, '_sock') as mock_sock:
        mock_sock.recvfrom.return_value = (b'{"invalid json"', None)

        # Should not crash
        await asyncio.wait_for(
            protocol._listen_loop(),
            timeout=0.5  # Enough for 1 iteration
        )

        # Peers should be empty (message rejected)
        assert len(protocol.peers) == 0
```

### Example 3: Signal Source All Fail
```python
def test_detector_resilient_to_all_signals_failing():
    """Test detector returns valid score even if all signals fail."""
    signals = [
        MagicMock(spec=SignalSource, read=MagicMock(side_effect=RuntimeError())),
        MagicMock(spec=SignalSource, read=MagicMock(side_effect=RuntimeError())),
        MagicMock(spec=SignalSource, read=MagicMock(side_effect=RuntimeError())),
    ]

    detector = IntentDetector(signals=signals)
    result = detector.detect()

    # Should return 0.0, not raise exception
    assert result.score == 0.0
    assert result.has_intent is False
```

---

**Report Generated:** 2026-02-26
**Analyst:** Test Coverage Analysis Tool
