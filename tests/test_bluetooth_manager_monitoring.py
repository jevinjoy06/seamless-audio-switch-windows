"""
Tests for BluetoothManager connection state monitoring.
"""

import time
from unittest.mock import MagicMock, patch

from src.bluetooth.manager import BluetoothManager


def test_start_monitoring_creates_background_thread():
    """Test that start_monitoring() creates a background monitoring thread."""
    callback = MagicMock()
    manager = BluetoothManager(
        target_address="AA:BB:CC:DD:EE:FF",
        on_disconnect_callback=callback
    )

    manager.start_monitoring()

    assert manager._monitor_thread is not None
    assert manager._monitor_thread.is_alive()
    assert manager._monitoring is True

    # Clean up
    manager.stop_monitoring()
    assert manager._monitoring is False


def test_disconnect_detection_triggers_callback():
    """Test that disconnect detection triggers the callback."""
    callback = MagicMock()
    manager = BluetoothManager(
        target_address="AA:BB:CC:DD:EE:FF",
        on_disconnect_callback=callback
    )

    # Simulate: connected → disconnected transition
    with patch.object(manager, "is_device_connected") as mock_connected:
        # Start with connected state
        manager._last_connection_state = "connected"
        mock_connected.return_value = False  # Now disconnected

        manager._check_connection_state()

        # Callback should be triggered once
        assert callback.call_count == 1


def test_disconnect_detection_no_callback_when_already_disconnected():
    """Test that callback is NOT triggered if already disconnected."""
    callback = MagicMock()
    manager = BluetoothManager(
        target_address="AA:BB:CC:DD:EE:FF",
        on_disconnect_callback=callback
    )

    # Both states disconnected (no transition)
    with patch.object(manager, "is_device_connected") as mock_connected:
        manager._last_connection_state = "disconnected"
        mock_connected.return_value = False

        manager._check_connection_state()

        # Callback should NOT be triggered
        assert callback.call_count == 0


def test_disconnect_detection_no_callback_when_connecting():
    """Test that callback is NOT triggered when going from disconnected to connected."""
    callback = MagicMock()
    manager = BluetoothManager(
        target_address="AA:BB:CC:DD:EE:FF",
        on_disconnect_callback=callback
    )

    # Transition: disconnected → connected (opposite direction)
    with patch.object(manager, "is_device_connected") as mock_connected:
        manager._last_connection_state = "disconnected"
        mock_connected.return_value = True  # Now connected

        manager._check_connection_state()

        # Callback should NOT be triggered
        assert callback.call_count == 0
