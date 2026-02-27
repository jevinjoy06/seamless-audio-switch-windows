# Testing Patterns

**Analysis Date:** 2026-02-27

## Test Framework

**Runner:**
- pytest 7.0+ (from `requirements.txt`: `pytest>=7.0`)
- pytest-asyncio 0.21+ for async test support (from `requirements.txt`: `pytest-asyncio>=0.21`)
- Config: No explicit `pytest.ini` or `setup.cfg` found; uses default pytest discovery

**Assertion Library:**
- Standard pytest assertions: `assert`, `assert x is True`, `assert x == y`

**Run Commands:**
```bash
pytest                     # Run all tests
pytest -v                  # Verbose output with test names
pytest tests/test_core.py # Run specific test file
pytest -k "test_yield"    # Run tests matching pattern
pytest --collect-only     # List all tests without running
```

## Test File Organization

**Location:**
- Co-located in `tests/` directory at project root, separate from source
- Mirror source structure not enforced; flat file naming preferred
- Tests directory: `/c/Users/jevin/Documents/seamless-audio-switch-windows/tests/`

**Naming:**
- Test files prefixed with `test_`: `test_core.py`, `test_integration.py`, `test_media_controller.py`
- Test functions prefixed with `test_`: `test_initial_state_is_idle()`, `test_full_integration_unexpected_disconnect()`
- Test classes prefixed with `Test`: `TestDeviceStateMachine`, `TestDeviceMessage`, `TestIntentDetector`, `TestCoordinationProtocol`

**Structure:**
```
tests/
├── test_core.py                        # Core state machine, message, intent, protocol tests
├── test_integration.py                 # Full component integration tests
├── test_media_controller.py            # MediaController pause/key send tests
├── test_coordination_pause.py          # Coordination protocol pause logic tests
├── test_bluetooth_manager_monitoring.py # Bluetooth monitoring callback tests
└── __init__.py
```

## Test Structure

**Suite Organization:**

Classes group related tests by component:
```python
class TestDeviceStateMachine:
    def test_initial_state_is_idle(self):
        sm = DeviceStateMachine()
        assert sm.state == DeviceState.IDLE

    def test_valid_transition_idle_to_intent(self):
        sm = DeviceStateMachine()
        assert sm.transition(DeviceState.INTENT_DETECTED) is True
        assert sm.state == DeviceState.INTENT_DETECTED
```

Flat functions for simple integration tests:
```python
def test_pause_sends_media_key():
    """Test that pause() sends VK_MEDIA_PLAY_PAUSE key."""
    controller = MediaController()
    with patch("ctypes.windll.user32.SendInput") as mock_send:
        mock_send.return_value = 2
        result = controller.pause()
        assert result is True
```

**Patterns:**

Setup pattern — Direct instantiation of objects with test-specific configuration:
```python
def test_self_messages_ignored(self):
    protocol = CoordinationProtocol(device_name="test")
    msg = DeviceMessage(
        device_id=protocol.device_id,
        device_name="test",
        intent_score=100.0,
        timestamp=time.time(),
        audio_state="playing",
        connection_state="requesting",
    )
```

Teardown pattern — None used; objects cleaned up automatically or tests are stateless

Assertion pattern — Arrange-Act-Assert style with descriptive assertions:
```python
# Arrange
protocol = CoordinationProtocol(device_name="test")
protocol.state_machine.transition(DeviceState.INTENT_DETECTED)

# Act
result = detector.detect()

# Assert
assert result.score == 100.0
assert result.has_intent is True
```

## Mocking

**Framework:** unittest.mock (from `from unittest.mock import MagicMock, patch`)

**Patterns:**

Mock external dependencies with context managers:
```python
from unittest.mock import patch, MagicMock

with patch("ctypes.windll.user32.SendInput") as mock_send:
    mock_send.return_value = 2
    result = controller.pause()
    assert mock_send.call_count == 1
```

Mock methods on class instances:
```python
with patch.object(protocol.media_controller, "pause") as mock_pause:
    mock_pause.return_value = True
    protocol._yield_connection()
    assert mock_pause.call_count == 1
```

Mock callbacks and side effects:
```python
disconnected = []
protocol = CoordinationProtocol(
    device_name="test",
    on_should_disconnect=lambda: disconnected.append(True),
)
protocol._yield_connection()
assert len(disconnected) == 1
```

Mock callback verification with MagicMock:
```python
disconnect_callback = MagicMock()
protocol = CoordinationProtocol(
    device_name="test",
    on_should_disconnect=disconnect_callback,
)
protocol._yield_connection()
assert disconnect_callback.call_count == 1
```

Mock time for testing delays:
```python
import time
with patch("time.time") as mock_time:
    mock_time.return_value = protocol._last_disconnect_time + 3.0
    protocol._handle_disconnect()
    assert mock_pause.call_count == 2  # Debounce timer elapsed
```

**What to Mock:**
- External system calls: `ctypes.windll.user32.SendInput()`, PowerShell subprocess calls
- Time-dependent operations: `time.time()` for debouncing tests
- Component dependencies in isolation tests: Mock `MediaController.pause()` when testing `CoordinationProtocol`
- Callbacks and event handlers: Mock `on_should_disconnect` to verify protocol triggers it

**What NOT to Mock:**
- Core business logic classes: Test `DeviceStateMachine`, `IntentDetector`, `CoordinationProtocol` with real instances
- Data structures: Use actual `DeviceMessage`, `PeerDevice`, `IntentResult` instances
- State management: Test actual state transitions, not mocked state
- Intent calculation: Use real `IntentDetector` with mock signal sources (see fixtures below)

## Fixtures and Factories

**Test Data:**

Mock signal source factory for intent testing:
```python
class MockSignal(SignalSource):
    def __init__(self, signal_name: str, value: float):
        self._name = signal_name
        self._value = value

    def name(self) -> str:
        return self._name

    def read(self) -> SignalReading:
        return SignalReading(
            source=self._name,
            value=self._value,
            timestamp=time.time(),
        )
```

Usage in tests:
```python
def test_max_score_when_all_active(self):
    signals = [
        MockSignal("audio_playing", 1.0),
        MockSignal("device_unlocked", 1.0),
        MockSignal("media_app_foreground", 1.0),
        MockSignal("interaction_recency", 1.0),
    ]
    detector = IntentDetector(signals=signals)
    result = detector.detect()
    assert result.score == 90.0
```

**Location:**
- Fixtures defined inline in test files: `test_core.py` defines `MockSignal` class inline
- No separate `conftest.py` or fixtures module found
- Simple factories preferred over pytest fixtures for flexibility

## Coverage

**Requirements:** Not enforced (no coverage configuration found)

**View Coverage:**
```bash
# To measure coverage (requires pytest-cov):
pytest --cov=src tests/
pytest --cov=src --cov-report=html tests/  # HTML report
```

Coverage not currently configured; measured manually if needed.

## Test Types

**Unit Tests:**
- Scope: Individual components in isolation
- Approach: Test method/function behavior with mock dependencies
- Examples:
  - `TestDeviceStateMachine` — state transitions, validation
  - `TestDeviceMessage` — serialization/deserialization
  - `TestIntentDetector` — scoring calculations with mock signals
  - `test_pause_sends_media_key()` — media controller key sending

**Integration Tests:**
- Scope: Multiple components working together
- Approach: Wire components, test workflows
- Examples:
  - `test_full_integration_unexpected_disconnect()` — BluetoothManager → CoordinationProtocol → MediaController
  - `test_full_integration_coordinated_yield()` — Coordinated handoff with state transitions
  - `test_yield_connection_pauses_before_disconnect()` — Pause then disconnect order

**E2E Tests:**
- Framework: Not used
- Reasoning: System requires Windows audio APIs and Bluetooth hardware; manual testing preferred

## Common Patterns

**Async Testing:**
- pytest-asyncio installed but not yet used in reviewed test files
- Async support available for future tests with `@pytest.mark.asyncio` decorator

**Error Testing:**
- Test both success and failure paths:
  ```python
  def test_pause_handles_sendinput_failure(self):
      controller = MediaController()
      with patch("ctypes.windll.user32.SendInput") as mock_send:
          mock_send.return_value = 0  # Failure
          result = controller.pause()
          assert result is False
  ```

- Test state validation preventing invalid operations:
  ```python
  def test_invalid_transition_rejected(self):
      sm = DeviceStateMachine()
      assert sm.transition(DeviceState.CONNECTED) is False
      assert sm.state == DeviceState.IDLE
  ```

**Debouncing Tests:**
- Time mocking to test rapid event sequences:
  ```python
  protocol._handle_disconnect()
  assert mock_pause.call_count == 1

  # Simulate time passing
  with patch("time.time") as mock_time:
      mock_time.return_value = protocol._last_disconnect_time + 3.0
      protocol._handle_disconnect()
      assert mock_pause.call_count == 2  # Second call after timeout
  ```

**State Machine Lifecycle Tests:**
- Walk full transition sequence to verify valid paths:
  ```python
  def test_valid_full_lifecycle(self):
      sm = DeviceStateMachine()
      assert sm.transition(DeviceState.INTENT_DETECTED)
      assert sm.transition(DeviceState.REQUESTING)
      assert sm.transition(DeviceState.CONNECTED)
      assert sm.transition(DeviceState.YIELDING)
      assert sm.transition(DeviceState.IDLE)
  ```

---

*Testing analysis: 2026-02-27*
