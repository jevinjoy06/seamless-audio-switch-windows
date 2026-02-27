# Windows Smart Yield Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Auto-pause media on Bluetooth handoff with cross-platform support (Windows ↔ Windows and iPhone → Windows)

**Architecture:** Add MediaController for universal pause via Win32 media keys, enhance BluetoothManager with connection monitoring, update CoordinationProtocol to pause before disconnect and handle unexpected disconnects.

**Tech Stack:** Python 3.10+, Win32 API (ctypes), WASAPI (existing), PowerShell, asyncio

---

## Task 1: MediaController - Core Pause Functionality

**Files:**
- Create: `src/coordinator/media.py`
- Create: `tests/test_media_controller.py`

**Step 1: Write the failing test**

```python
# tests/test_media_controller.py
"""Tests for MediaController - media playback control via Win32 keys."""

import unittest
from unittest.mock import patch, MagicMock
from src.coordinator.media import MediaController


class TestMediaController(unittest.TestCase):
    def test_pause_sends_media_key(self):
        """Verify pause() sends VK_MEDIA_PLAY_PAUSE key via SendInput."""
        controller = MediaController()

        with patch('src.coordinator.media.ctypes.windll.user32.SendInput') as mock_send:
            mock_send.return_value = 1  # Success
            result = controller.pause()

            # Verify SendInput was called once
            self.assertEqual(mock_send.call_count, 1)
            self.assertTrue(result)

    def test_pause_handles_failure(self):
        """Verify pause() returns False and logs error on Win32 failure."""
        controller = MediaController()

        with patch('src.coordinator.media.ctypes.windll.user32.SendInput') as mock_send:
            mock_send.return_value = 0  # Failure

            with self.assertLogs('src.coordinator.media', level='WARNING'):
                result = controller.pause()

            self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_media_controller.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.coordinator.media'`

**Step 3: Write minimal implementation**

```python
# src/coordinator/media.py
"""
MediaController — Controls media playback on Windows via Win32 APIs.

Sends media key commands (play/pause) using SendInput to control
any media app that responds to Windows media keys.
"""

import ctypes
import logging
from ctypes import wintypes

logger = logging.getLogger(__name__)

# Win32 constants
VK_MEDIA_PLAY_PAUSE = 0xB3
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]

    _fields_ = [
        ("type", wintypes.DWORD),
        ("_input", _INPUT),
    ]


class MediaController:
    """
    Controls media playback on Windows via Win32 media keys.

    Usage:
        controller = MediaController()
        controller.pause()  # Sends VK_MEDIA_PLAY_PAUSE
    """

    def __init__(self):
        self._user32 = ctypes.windll.user32

    def pause(self) -> bool:
        """
        Send VK_MEDIA_PLAY_PAUSE key to pause/resume media.

        Works with: Spotify, Chrome, VLC, Windows Media Player,
        and any app that responds to Windows media keys.

        Returns:
            True if key was sent successfully, False otherwise.
        """
        try:
            # Key down
            input_down = INPUT()
            input_down.type = INPUT_KEYBOARD
            input_down._input.ki = KEYBDINPUT(
                wVk=VK_MEDIA_PLAY_PAUSE,
                wScan=0,
                dwFlags=0,
                time=0,
                dwExtraInfo=None,
            )

            # Key up
            input_up = INPUT()
            input_up.type = INPUT_KEYBOARD
            input_up._input.ki = KEYBDINPUT(
                wVk=VK_MEDIA_PLAY_PAUSE,
                wScan=0,
                dwFlags=KEYEVENTF_KEYUP,
                time=0,
                dwExtraInfo=None,
            )

            # Send both events
            inputs = (INPUT * 2)(input_down, input_up)
            result = self._user32.SendInput(2, inputs, ctypes.sizeof(INPUT))

            if result != 2:
                logger.warning(f"SendInput failed: returned {result}, expected 2")
                return False

            logger.debug("Media pause key sent successfully")
            return True

        except Exception as e:
            logger.warning(f"Failed to send media pause key: {e}")
            return False
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_media_controller.py -v`

Expected: PASS (2 tests passed)

**Step 5: Commit**

```bash
git add src/coordinator/media.py tests/test_media_controller.py
git commit -m "feat: add MediaController for Win32 media key control

Implements universal media pause via VK_MEDIA_PLAY_PAUSE key.
Works with Spotify, Chrome, VLC, and other media apps.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 2: BluetoothManager - Connection State Monitoring

**Files:**
- Modify: `src/bluetooth/manager.py`
- Create: `tests/test_bluetooth_monitor.py`

**Step 1: Write the failing test**

```python
# tests/test_bluetooth_monitor.py
"""Tests for BluetoothManager connection monitoring."""

import unittest
import time
from unittest.mock import Mock, patch
from src.bluetooth.manager import BluetoothManager


class TestBluetoothMonitoring(unittest.TestCase):
    def test_disconnect_callback_triggered(self):
        """Verify on_disconnect_callback is called when connection lost."""
        callback = Mock()
        manager = BluetoothManager(
            target_device="AA:BB:CC:DD:EE:FF",
            on_disconnect_callback=callback
        )

        # Simulate: connected, then disconnected
        with patch.object(manager, 'is_connected') as mock_connected:
            mock_connected.side_effect = [True, False]  # Was connected, now disconnected

            manager._check_connection_state()

            # Callback should be triggered
            callback.assert_called_once()

    def test_no_callback_when_already_disconnected(self):
        """Verify callback not triggered if already disconnected."""
        callback = Mock()
        manager = BluetoothManager(
            target_device="AA:BB:CC:DD:EE:FF",
            on_disconnect_callback=callback
        )

        with patch.object(manager, 'is_connected', return_value=False):
            manager._check_connection_state()
            manager._check_connection_state()  # Still disconnected

            # Callback should only be called once
            self.assertEqual(callback.call_count, 1)


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_bluetooth_monitor.py -v`

Expected: FAIL with `AttributeError: 'BluetoothManager' object has no attribute '_check_connection_state'`

**Step 3: Read current BluetoothManager implementation**

Read: `src/bluetooth/manager.py` to understand existing structure

**Step 4: Add monitoring functionality**

```python
# Add to src/bluetooth/manager.py

import threading
import time
from typing import Callable, Optional

class BluetoothManager:
    """
    Manages Bluetooth connections on Windows with connection monitoring.

    New features:
    - Background monitoring thread
    - Disconnect callback mechanism
    """

    def __init__(
        self,
        target_device: str,
        on_disconnect_callback: Optional[Callable] = None
    ):
        self.target_device = target_device
        self._on_disconnect = on_disconnect_callback
        self._connection_state = "disconnected"
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_running = False
        self._last_known_state = "disconnected"

    def start_monitoring(self, interval: float = 1.0) -> None:
        """
        Start background thread that monitors Bluetooth connection state.

        Args:
            interval: Check interval in seconds (default: 1.0)
        """
        if self._monitor_running:
            return

        self._monitor_running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True
        )
        self._monitor_thread.start()
        logger.info(f"Bluetooth monitoring started for {self.target_device}")

    def stop_monitoring(self) -> None:
        """Stop the background monitoring thread."""
        self._monitor_running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
            logger.info("Bluetooth monitoring stopped")

    def _monitor_loop(self, interval: float) -> None:
        """Background loop that checks connection state periodically."""
        while self._monitor_running:
            try:
                self._check_connection_state()
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
            time.sleep(interval)

    def _check_connection_state(self) -> None:
        """
        Check current connection state and trigger callback if disconnected.

        Only triggers callback on transition from connected → disconnected.
        """
        try:
            current_state = "connected" if self.is_connected() else "disconnected"

            # Detect transition from connected to disconnected
            if self._last_known_state == "connected" and current_state == "disconnected":
                logger.info(f"Bluetooth disconnect detected: {self.target_device}")
                if self._on_disconnect:
                    self._on_disconnect()

            self._last_known_state = current_state

        except Exception as e:
            logger.error(f"Failed to check connection state: {e}")
            # Assume disconnected on error (safe default)
            if self._last_known_state == "connected":
                logger.warning("Assuming disconnected due to error")
                if self._on_disconnect:
                    self._on_disconnect()
                self._last_known_state = "disconnected"

    def is_connected(self) -> bool:
        """
        Check if the target Bluetooth device is currently connected.

        Uses PowerShell to query PnP device status.

        Returns:
            True if connected, False otherwise.
        """
        try:
            import subprocess

            # Query device status via PowerShell
            cmd = [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Get-PnpDevice | Where-Object {{$_.FriendlyName -like '*{self.target_device}*'}} | Select-Object -ExpandProperty Status"
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5
            )

            # Device is connected if status is "OK"
            return "OK" in result.stdout

        except Exception as e:
            logger.error(f"Failed to check Bluetooth connection: {e}")
            return False

    # ... rest of existing methods (connect, disconnect, etc.)
```

**Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_bluetooth_monitor.py -v`

Expected: PASS (2 tests passed)

**Step 6: Commit**

```bash
git add src/bluetooth/manager.py tests/test_bluetooth_monitor.py
git commit -m "feat: add Bluetooth connection monitoring

- Background thread polls connection state (1s interval)
- Callback mechanism for disconnect events
- Safe error handling (assume disconnected on failure)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 3: CoordinationProtocol - Pause on Coordinated Yield

**Files:**
- Modify: `src/coordinator/protocol.py`
- Create: `tests/test_coordinated_pause.py`

**Step 1: Write the failing test**

```python
# tests/test_coordinated_pause.py
"""Tests for coordinated yield with auto-pause."""

import unittest
from unittest.mock import Mock, patch
from src.coordinator.protocol import CoordinationProtocol
from src.coordinator.state import DeviceState


class TestCoordinatedPause(unittest.TestCase):
    def test_yield_pauses_then_disconnects(self):
        """Verify _yield_connection pauses media BEFORE disconnecting."""
        mock_bt_manager = Mock()
        mock_disconnect_callback = Mock()

        protocol = CoordinationProtocol(
            device_name="test-device",
            bluetooth_manager=mock_bt_manager,
            on_should_disconnect=mock_disconnect_callback
        )

        # Mock media controller
        with patch.object(protocol.media_controller, 'pause') as mock_pause:
            protocol._yield_connection()

            # Verify pause was called
            mock_pause.assert_called_once()

            # Verify disconnect was called
            mock_disconnect_callback.assert_called_once()

            # Verify state transitioned to YIELDING
            self.assertEqual(protocol.state_machine.state, DeviceState.YIELDING)

    def test_pause_happens_before_disconnect(self):
        """Verify pause is called BEFORE disconnect callback."""
        mock_bt_manager = Mock()
        call_order = []

        def track_pause():
            call_order.append('pause')

        def track_disconnect():
            call_order.append('disconnect')

        protocol = CoordinationProtocol(
            device_name="test-device",
            bluetooth_manager=mock_bt_manager,
            on_should_disconnect=track_disconnect
        )

        with patch.object(protocol.media_controller, 'pause', side_effect=track_pause):
            protocol._yield_connection()

            # Verify order: pause THEN disconnect
            self.assertEqual(call_order, ['pause', 'disconnect'])


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_coordinated_pause.py -v`

Expected: FAIL with `AttributeError: 'CoordinationProtocol' object has no attribute 'bluetooth_manager'`

**Step 3: Read current CoordinationProtocol implementation**

Read: `src/coordinator/protocol.py` to understand current structure

**Step 4: Update CoordinationProtocol to add MediaController**

```python
# Add to src/coordinator/protocol.py

from src.coordinator.media import MediaController

class CoordinationProtocol:
    """
    UDP-based coordination protocol with auto-pause on handoff.

    New features:
    - MediaController integration for auto-pause
    - Bluetooth manager reference for disconnect handling
    """

    def __init__(
        self,
        device_name: str,
        port: int = DEFAULT_PORT,
        device_id: Optional[str] = None,
        bluetooth_manager: Optional['BluetoothManager'] = None,
        on_should_connect: Optional[Callable] = None,
        on_should_disconnect: Optional[Callable] = None,
    ):
        self.device_id = device_id or str(uuid.uuid4())
        self.device_name = device_name
        self.port = port
        self.peers: dict[str, PeerDevice] = {}
        self.state_machine = DeviceStateMachine()
        self.intent_score: float = 0.0
        self.audio_state: str = "idle"

        # Bluetooth manager and media controller
        self.bluetooth_manager = bluetooth_manager
        self.media_controller = MediaController()

        # Callbacks
        self._on_should_connect = on_should_connect
        self._on_should_disconnect = on_should_disconnect

        self._sock: Optional[socket.socket] = None
        self._running = False

    def _yield_connection(self) -> None:
        """
        Yield audio connection to higher-priority peer device.

        Steps:
        1. Transition to YIELDING state
        2. Pause media (via MediaController)
        3. Trigger Bluetooth disconnect (via callback)
        """
        self.state_machine.transition(DeviceState.YIELDING)
        logger.info("Yielding audio connection to peer device")

        # CRITICAL: Pause BEFORE disconnect
        pause_success = self.media_controller.pause()
        if not pause_success:
            logger.warning("Media pause failed, continuing with disconnect")

        # Trigger Bluetooth disconnect
        if self._on_should_disconnect:
            self._on_should_disconnect()
```

**Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_coordinated_pause.py -v`

Expected: PASS (2 tests passed)

**Step 6: Commit**

```bash
git add src/coordinator/protocol.py tests/test_coordinated_pause.py
git commit -m "feat: add auto-pause on coordinated yield

When yielding to Windows peer:
1. Pause media via MediaController
2. Then disconnect Bluetooth

Ensures smooth handoff with no audio overlap.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 4: CoordinationProtocol - Handle Unexpected Disconnects

**Files:**
- Modify: `src/coordinator/protocol.py`
- Create: `tests/test_unexpected_disconnect.py`

**Step 1: Write the failing test**

```python
# tests/test_unexpected_disconnect.py
"""Tests for unexpected disconnect handling (iPhone takeover, manual disconnect)."""

import unittest
import time
from unittest.mock import Mock, patch
from src.coordinator.protocol import CoordinationProtocol
from src.coordinator.state import DeviceState


class TestUnexpectedDisconnect(unittest.TestCase):
    def test_unexpected_disconnect_triggers_pause(self):
        """Verify unexpected disconnect (iPhone takeover) triggers pause."""
        mock_bt_manager = Mock()

        protocol = CoordinationProtocol(
            device_name="test-device",
            bluetooth_manager=mock_bt_manager
        )

        # Simulate CONNECTED state
        protocol.state_machine.transition(DeviceState.CONNECTED)

        with patch.object(protocol.media_controller, 'pause') as mock_pause:
            protocol._handle_disconnect()

            # Verify pause was called
            mock_pause.assert_called_once()

            # Verify state transitioned to IDLE
            self.assertEqual(protocol.state_machine.state, DeviceState.IDLE)

    def test_yielding_disconnect_does_not_double_pause(self):
        """Verify disconnect during YIELDING state doesn't trigger extra pause."""
        mock_bt_manager = Mock()

        protocol = CoordinationProtocol(
            device_name="test-device",
            bluetooth_manager=mock_bt_manager
        )

        # Simulate YIELDING state (already paused)
        protocol.state_machine.transition(DeviceState.YIELDING)

        with patch.object(protocol.media_controller, 'pause') as mock_pause:
            protocol._handle_disconnect()

            # Verify pause was NOT called (already paused in _yield_connection)
            mock_pause.assert_not_called()

    def test_debounce_rapid_disconnects(self):
        """Verify rapid disconnects are debounced (only first triggers pause)."""
        mock_bt_manager = Mock()

        protocol = CoordinationProtocol(
            device_name="test-device",
            bluetooth_manager=mock_bt_manager
        )

        protocol.state_machine.transition(DeviceState.CONNECTED)

        with patch.object(protocol.media_controller, 'pause') as mock_pause:
            # First disconnect
            protocol._handle_disconnect()

            # Second disconnect within 2 seconds (should be ignored)
            protocol.state_machine.transition(DeviceState.CONNECTED)  # Reset for test
            protocol._handle_disconnect()

            # Verify pause was only called once (debounced)
            self.assertEqual(mock_pause.call_count, 1)


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_unexpected_disconnect.py -v`

Expected: FAIL with `AttributeError: 'CoordinationProtocol' object has no attribute '_handle_disconnect'`

**Step 3: Implement unexpected disconnect handler with debouncing**

```python
# Add to src/coordinator/protocol.py

class CoordinationProtocol:
    def __init__(self, ...):
        # ... existing init code ...

        # Debouncing for rapid disconnects
        self._last_disconnect_time: float = 0.0
        self._debounce_interval: float = 2.0  # seconds

        # Register disconnect callback with Bluetooth manager
        if bluetooth_manager:
            bluetooth_manager.on_disconnect_callback = self._handle_disconnect

    def _handle_disconnect(self) -> None:
        """
        Handle unexpected Bluetooth disconnect.

        Scenarios:
        1. During YIELDING state → Expected disconnect, already paused
        2. iPhone takeover → Pause media, go IDLE
        3. Manual disconnect → Pause media, go IDLE
        4. Rapid disconnects → Debounce (ignore within 2s of last)
        """
        # Skip if we're already yielding (expected disconnect)
        if self.state_machine.state == DeviceState.YIELDING:
            logger.debug("Disconnect during yield - expected, skipping")
            return

        # Debounce rapid disconnects
        now = time.time()
        if now - self._last_disconnect_time < self._debounce_interval:
            logger.debug("Ignoring rapid disconnect (debounce)")
            return

        self._last_disconnect_time = now

        # Unexpected disconnect → pause and go IDLE
        logger.info("Bluetooth disconnected unexpectedly - pausing media")

        pause_success = self.media_controller.pause()
        if not pause_success:
            logger.warning("Media pause failed on disconnect")

        self.state_machine.transition(DeviceState.IDLE)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_unexpected_disconnect.py -v`

Expected: PASS (3 tests passed)

**Step 5: Commit**

```bash
git add src/coordinator/protocol.py tests/test_unexpected_disconnect.py
git commit -m "feat: handle unexpected Bluetooth disconnects

Auto-pause on:
- iPhone takeover (external handoff)
- Manual disconnect
- Headphones power off

Features:
- Debouncing (2s) to prevent spam on flaky connections
- Skip during YIELDING to avoid double-pause

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 5: Integration - Wire Up All Components

**Files:**
- Modify: `src/coordinator/protocol.py` (main entry point)
- Create: `tests/test_integration.py`

**Step 1: Write integration test**

```python
# tests/test_integration.py
"""Integration tests for complete handoff flow."""

import unittest
import time
from unittest.mock import Mock, patch
from src.coordinator.protocol import CoordinationProtocol
from src.bluetooth.manager import BluetoothManager
from src.coordinator.state import DeviceState


class TestIntegration(unittest.TestCase):
    def test_full_coordinated_handoff(self):
        """Test complete Windows peer handoff: pause → disconnect → IDLE."""
        # Setup
        mock_bt_manager = BluetoothManager(
            target_device="AA:BB:CC:DD:EE:FF"
        )

        disconnect_called = False
        def mock_disconnect():
            nonlocal disconnect_called
            disconnect_called = True

        protocol = CoordinationProtocol(
            device_name="laptop-1",
            bluetooth_manager=mock_bt_manager,
            on_should_disconnect=mock_disconnect
        )

        # Simulate connected state
        protocol.state_machine.transition(DeviceState.CONNECTED)
        protocol.intent_score = 50

        # Act: Yield to peer
        with patch.object(protocol.media_controller, 'pause', return_value=True):
            protocol._yield_connection()

        # Assert
        self.assertTrue(disconnect_called)
        self.assertEqual(protocol.state_machine.state, DeviceState.YIELDING)

    def test_iphone_takeover_flow(self):
        """Test iPhone takeover: detect disconnect → pause → IDLE."""
        # Setup
        mock_bt_manager = BluetoothManager(
            target_device="AA:BB:CC:DD:EE:FF"
        )

        protocol = CoordinationProtocol(
            device_name="laptop-1",
            bluetooth_manager=mock_bt_manager
        )

        protocol.state_machine.transition(DeviceState.CONNECTED)

        # Act: Simulate iPhone takeover (unexpected disconnect)
        with patch.object(protocol.media_controller, 'pause', return_value=True):
            protocol._handle_disconnect()

        # Assert
        self.assertEqual(protocol.state_machine.state, DeviceState.IDLE)


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run test to verify current state**

Run: `python -m pytest tests/test_integration.py -v`

Expected: Tests may pass or reveal integration issues

**Step 3: Update main entry point to wire components together**

```python
# Update main() in src/coordinator/protocol.py

async def main():
    import argparse
    from src.bluetooth.manager import BluetoothManager

    parser = argparse.ArgumentParser(description="Seamless Audio Switch Coordinator")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--name", default=socket.gethostname(), help="Device name")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="UDP port")
    parser.add_argument("--bt-device", required=True, help="Bluetooth device MAC address")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize Bluetooth manager
    bt_manager = BluetoothManager(
        target_device=args.bt_device
    )

    # Initialize coordination protocol with Bluetooth manager
    protocol = CoordinationProtocol(
        device_name=args.name,
        port=args.port,
        bluetooth_manager=bt_manager,
        on_should_connect=bt_manager.connect,
        on_should_disconnect=bt_manager.disconnect,
    )

    # Start Bluetooth monitoring
    bt_manager.start_monitoring()

    logger.info(f"Windows Smart Yield started for {args.bt_device}")
    logger.info(f"Device: {args.name}, Port: {args.port}")

    try:
        await protocol.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        bt_manager.stop_monitoring()
        await protocol.stop()


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 4: Run integration tests**

Run: `python -m pytest tests/test_integration.py -v`

Expected: PASS (2 tests passed)

**Step 5: Manual smoke test**

Run: `python -m src.coordinator.protocol --bt-device AA:BB:CC:DD:EE:FF --name test-laptop`

Expected: Application starts, logs show monitoring enabled

**Step 6: Commit**

```bash
git add src/coordinator/protocol.py tests/test_integration.py
git commit -m "feat: wire up components for Windows Smart Yield

Complete integration:
- BluetoothManager monitoring starts on launch
- CoordinationProtocol has MediaController
- Disconnect callbacks properly registered
- Main entry point accepts --bt-device arg

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 6: Update Configuration and Documentation

**Files:**
- Modify: `config.example.yaml`
- Modify: `README.md`
- Create: `docs/windows-smart-yield.md`

**Step 1: Update config.example.yaml with new settings**

```yaml
# Add to config.example.yaml

bluetooth:
  # Target audio device MAC address (required)
  target_device: "AA:BB:CC:DD:EE:FF"

  # Auto-pause settings
  auto_pause:
    enabled: true
    # Debounce interval for rapid disconnects (seconds)
    debounce_interval: 2.0

  # Connection monitoring
  monitoring:
    enabled: true
    # How often to check connection state (seconds)
    poll_interval: 1.0

  # Link key sync (existing)
  key_sync:
    enabled: true
    encryption: "aes-256-gcm"
```

**Step 2: Update README.md with Windows Smart Yield feature**

```markdown
# Add to README.md after "How It Works" section

## Windows Smart Yield

Automatic media pause on Bluetooth handoff — works with Windows peers and Apple devices (iPhone, iPad, Mac).

### Cross-Platform Support

✅ **iPhone → Windows**: When iPhone takes your AirPods, Windows auto-pauses
✅ **Windows ↔ Windows**: Coordinated handoff with auto-pause
⚠️ **Windows → iPhone**: Windows connects, but can't auto-pause iPhone (iOS limitation)

### How It Works

1. **Coordinated Handoff (Windows Peer Wins)**
   - Peer device starts playing → broadcasts high intent score
   - This device sees higher score → pauses media → disconnects Bluetooth
   - Peer device connects and plays

2. **External Handoff (iPhone Takes Over)**
   - iPhone connects to AirPods (Apple's native handoff)
   - Windows detects disconnect → pauses media

3. **Manual Disconnect**
   - User turns off headphones
   - Windows detects disconnect → pauses media

### Configuration

See `config.example.yaml` for auto-pause settings:
- Enable/disable auto-pause
- Debounce interval (prevents spam on flaky connections)
- Monitoring poll interval
```

**Step 3: Create detailed documentation**

```markdown
# Create docs/windows-smart-yield.md

# Windows Smart Yield

## Overview

Windows Smart Yield provides automatic media pause on Bluetooth handoff, replicating the Apple ecosystem experience on Windows.

## Architecture

### Components

1. **MediaController** (`src/coordinator/media.py`)
   - Sends VK_MEDIA_PLAY_PAUSE via Win32 SendInput
   - Universal compatibility with media apps

2. **BluetoothManager** (`src/bluetooth/manager.py`)
   - Background monitoring thread (polls every 1s)
   - Disconnect event detection
   - Callback mechanism for coordinator

3. **CoordinationProtocol** (`src/coordinator/protocol.py`)
   - Orchestrates handoff logic
   - Distinguishes: coordinated yield vs unexpected disconnect
   - Triggers pause at appropriate times

### Handoff Scenarios

#### Scenario 1: Windows Peer Wins
```
Laptop-1 (you): Playing music, score=50
Laptop-2: Starts music, score=70

Flow:
1. Laptop-1 sees score=70 > 50
2. Laptop-1: Pause media
3. Laptop-1: Disconnect Bluetooth
4. Laptop-2: Connect Bluetooth
5. Laptop-2: Music plays
```

#### Scenario 2: iPhone Takes Over
```
Windows: Playing music, connected to AirPods
iPhone: User plays music

Flow:
1. iPhone connects to AirPods (Apple's handoff)
2. Windows: Detects Bluetooth disconnect
3. Windows: Pause media
4. Windows: Go IDLE
```

## Testing

### Unit Tests
```bash
pytest tests/test_media_controller.py -v
pytest tests/test_bluetooth_monitor.py -v
pytest tests/test_coordinated_pause.py -v
pytest tests/test_unexpected_disconnect.py -v
pytest tests/test_integration.py -v
```

### Manual Testing

**Test 1: Windows ↔ Windows**
1. Run app on two Windows devices
2. Play music on Device A
3. Start music on Device B
4. Verify: Device A pauses, Device B connects

**Test 2: iPhone → Windows**
1. Run app on Windows
2. Play music on Windows
3. Play music on iPhone
4. Verify: Windows pauses when iPhone connects

**Test 3: Manual Disconnect**
1. Play music on Windows
2. Turn off headphones
3. Verify: Windows pauses

## Troubleshooting

### Media doesn't pause
- Check logs for "Failed to send media pause key"
- Verify media app supports Windows media keys
- Try testing with Spotify or Chrome first

### Disconnect not detected
- Check logs for Bluetooth monitoring errors
- Verify PowerShell can query PnP devices
- Check `--bt-device` MAC address is correct

### Rapid pause/unpause
- Flaky Bluetooth connection
- Debouncing should prevent this (2s interval)
- Check logs for "Ignoring rapid disconnect"

## Limitations

- **iPhone → Windows works perfectly**
- **Windows → iPhone**: iPhone won't auto-pause (iOS restriction)
  - Workaround: Manually pause iPhone or switch via Control Center
- Media pause is universal (pauses all audio, not just specific apps)
```

**Step 4: Commit documentation**

```bash
git add config.example.yaml README.md docs/windows-smart-yield.md
git commit -m "docs: add Windows Smart Yield documentation

- Updated config with auto-pause settings
- Added README section explaining cross-platform support
- Created detailed docs/windows-smart-yield.md

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 7: Run Full Test Suite and Verify

**Step 1: Run all tests**

Run: `python -m pytest tests/ -v --tb=short`

Expected: All tests pass

**Step 2: Check test coverage (optional)**

Run: `python -m pytest tests/ --cov=src --cov-report=term-missing`

Expected: >80% coverage on modified files

**Step 3: Run linter**

Run: `python -m flake8 src/ tests/ --max-line-length=100`

Expected: No errors

**Step 4: Manual end-to-end test**

1. Start app: `python -m src.coordinator.protocol --bt-device AA:BB:CC:DD:EE:FF`
2. Play music on Windows
3. Simulate iPhone takeover (manually disconnect Bluetooth)
4. Verify: Music paused ✓
5. Reconnect Bluetooth manually
6. Verify: Music stays paused (no auto-resume) ✓

**Step 5: Final commit**

```bash
git add .
git commit -m "test: verify Windows Smart Yield complete implementation

All tests passing:
- Unit tests for all components
- Integration tests for handoff flows
- Manual testing completed

Ready for production use.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Success Criteria

✅ MediaController sends VK_MEDIA_PLAY_PAUSE successfully
✅ BluetoothManager monitors connection state in background
✅ CoordinationProtocol pauses before disconnect on yield
✅ Unexpected disconnects trigger pause
✅ Debouncing prevents rapid disconnect spam
✅ All unit tests pass
✅ Integration tests pass
✅ Manual testing confirms Windows + iPhone handoff works
✅ Documentation complete

---

## Future Enhancements (Not in Scope)

- Apple-style notification UI (separate feature)
- Auto-resume on reconnect (explicitly rejected by user)
- BLE coordination for better Apple device detection
- Per-app pause control (pause Spotify but not system sounds)

---

## Notes for Engineer

- **YAGNI**: Only implement what's in this plan. No extra features.
- **TDD**: Write test first, see it fail, implement, see it pass, commit.
- **DRY**: Reuse existing signal detection from `src/intent/signals.py` if needed.
- **Frequent commits**: Every task ends with a commit.
- **Error handling**: Graceful degradation (log errors, continue operation).
- **Windows only**: No need for cross-platform abstractions yet.

Good luck! 🚀
