"""
Tests for CoordinationProtocol pause integration.
"""

from unittest.mock import MagicMock, patch

from src.coordinator.protocol import CoordinationProtocol
from src.coordinator.state import DeviceState


def test_yield_connection_pauses_before_disconnect():
    """Test that _yield_connection() pauses media before disconnecting."""
    on_disconnect = MagicMock()
    protocol = CoordinationProtocol(
        device_name="test-device",
        on_should_disconnect=on_disconnect
    )

    # Set up valid state: must be CONNECTED to yield
    protocol.state_machine.transition(DeviceState.INTENT_DETECTED)
    protocol.state_machine.transition(DeviceState.REQUESTING)
    protocol.state_machine.transition(DeviceState.CONNECTED)

    with patch.object(protocol.media_controller, "pause") as mock_pause:
        mock_pause.return_value = True

        protocol._yield_connection()

        # Verify pause was called
        assert mock_pause.call_count == 1

        # Verify disconnect was called after pause
        assert on_disconnect.call_count == 1

        # Verify state transition
        assert protocol.state_machine.state == DeviceState.YIELDING


def test_yield_connection_continues_even_if_pause_fails():
    """Test that disconnect happens even if pause fails."""
    on_disconnect = MagicMock()
    protocol = CoordinationProtocol(
        device_name="test-device",
        on_should_disconnect=on_disconnect
    )

    # Set up valid state: must be CONNECTED to yield
    protocol.state_machine.transition(DeviceState.INTENT_DETECTED)
    protocol.state_machine.transition(DeviceState.REQUESTING)
    protocol.state_machine.transition(DeviceState.CONNECTED)

    with patch.object(protocol.media_controller, "pause") as mock_pause:
        mock_pause.return_value = False  # Pause fails

        protocol._yield_connection()

        # Pause was attempted
        assert mock_pause.call_count == 1

        # Disconnect still happens
        assert on_disconnect.call_count == 1


def test_handle_disconnect_pauses_and_goes_idle():
    """Test that unexpected disconnect triggers pause and IDLE state."""
    protocol = CoordinationProtocol(device_name="test-device")

    # Set up: device is CONNECTED
    protocol.state_machine.transition(DeviceState.INTENT_DETECTED)
    protocol.state_machine.transition(DeviceState.REQUESTING)
    protocol.state_machine.transition(DeviceState.CONNECTED)

    with patch.object(protocol.media_controller, "pause") as mock_pause:
        mock_pause.return_value = True

        protocol._handle_disconnect()

        # Pause was called
        assert mock_pause.call_count == 1

        # State transitioned to IDLE
        assert protocol.state_machine.state == DeviceState.IDLE


def test_handle_disconnect_ignores_when_yielding():
    """Test that disconnect is ignored when in YIELDING state (expected disconnect)."""
    protocol = CoordinationProtocol(device_name="test-device")

    # Set up: device is YIELDING (expected disconnect)
    protocol.state_machine.transition(DeviceState.INTENT_DETECTED)
    protocol.state_machine.transition(DeviceState.REQUESTING)
    protocol.state_machine.transition(DeviceState.CONNECTED)
    protocol.state_machine.transition(DeviceState.YIELDING)

    with patch.object(protocol.media_controller, "pause") as mock_pause:
        protocol._handle_disconnect()

        # Pause should NOT be called (expected disconnect)
        assert mock_pause.call_count == 0

        # State remains YIELDING
        assert protocol.state_machine.state == DeviceState.YIELDING


def test_handle_disconnect_debouncing():
    """Test that rapid disconnects are debounced (2 second interval)."""
    protocol = CoordinationProtocol(device_name="test-device")
    protocol.state_machine.transition(DeviceState.INTENT_DETECTED)
    protocol.state_machine.transition(DeviceState.REQUESTING)
    protocol.state_machine.transition(DeviceState.CONNECTED)

    with patch.object(protocol.media_controller, "pause") as mock_pause:
        mock_pause.return_value = True

        # First disconnect - should trigger pause
        protocol._handle_disconnect()
        assert mock_pause.call_count == 1

        # Go back to CONNECTED to simulate rapid reconnect/disconnect
        protocol.state_machine.transition(DeviceState.INTENT_DETECTED)
        protocol.state_machine.transition(DeviceState.REQUESTING)
        protocol.state_machine.transition(DeviceState.CONNECTED)

        # Second disconnect within 2 seconds - should be debounced
        protocol._handle_disconnect()
        assert mock_pause.call_count == 1  # Still 1, not 2

        # Simulate time passing (mock time)
        import time
        with patch("time.time") as mock_time:
            mock_time.return_value = protocol._last_disconnect_time + 3.0

            protocol.state_machine.transition(DeviceState.INTENT_DETECTED)
            protocol.state_machine.transition(DeviceState.REQUESTING)
            protocol.state_machine.transition(DeviceState.CONNECTED)

            # Third disconnect after 3 seconds - should trigger again
            protocol._handle_disconnect()
            assert mock_pause.call_count == 2
