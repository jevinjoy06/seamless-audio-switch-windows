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
