"""
Integration tests for Windows Smart Yield components.

Tests that BluetoothManager, CoordinationProtocol, and MediaController
are properly wired together.
"""

from unittest.mock import MagicMock, patch

from src.bluetooth.manager import BluetoothManager
from src.coordinator.protocol import CoordinationProtocol
from src.coordinator.state import DeviceState


def test_full_integration_unexpected_disconnect():
    """Test full integration: Bluetooth disconnect triggers pause."""
    # Create BluetoothManager with callback placeholder
    bt_manager = BluetoothManager(target_address="AA:BB:CC:DD:EE:FF")

    # Create CoordinationProtocol and wire to BluetoothManager
    protocol = CoordinationProtocol(
        device_name="test-device",
        bluetooth_manager=bt_manager
    )

    # Verify callback is registered
    assert bt_manager._on_disconnect is not None
    assert bt_manager._on_disconnect == protocol._handle_disconnect

    # Simulate device being connected
    protocol.state_machine.transition(DeviceState.INTENT_DETECTED)
    protocol.state_machine.transition(DeviceState.REQUESTING)
    protocol.state_machine.transition(DeviceState.CONNECTED)

    # Mock the media controller pause
    with patch.object(protocol.media_controller, "pause") as mock_pause:
        mock_pause.return_value = True

        # Simulate Bluetooth disconnect triggering callback
        bt_manager._on_disconnect()

        # Verify pause was called
        assert mock_pause.call_count == 1

        # Verify state transitioned to IDLE
        assert protocol.state_machine.state == DeviceState.IDLE


def test_full_integration_coordinated_yield():
    """Test full integration: Coordinated yield pauses before disconnect."""
    # Create components
    bt_manager = BluetoothManager(target_address="AA:BB:CC:DD:EE:FF")
    disconnect_callback = MagicMock()

    protocol = CoordinationProtocol(
        device_name="test-device",
        on_should_disconnect=disconnect_callback,
        bluetooth_manager=bt_manager
    )

    # Set up connected state
    protocol.state_machine.transition(DeviceState.INTENT_DETECTED)
    protocol.state_machine.transition(DeviceState.REQUESTING)
    protocol.state_machine.transition(DeviceState.CONNECTED)

    with patch.object(protocol.media_controller, "pause") as mock_pause:
        mock_pause.return_value = True

        # Trigger coordinated yield
        protocol._yield_connection()

        # Verify pause was called
        assert mock_pause.call_count == 1

        # Verify disconnect callback was triggered
        assert disconnect_callback.call_count == 1

        # Verify state is YIELDING
        assert protocol.state_machine.state == DeviceState.YIELDING

        # Now simulate the actual disconnect from BluetoothManager
        bt_manager._on_disconnect()

        # Pause should NOT be called again (already in YIELDING state)
        assert mock_pause.call_count == 1  # Still 1, not 2
