"""
Tests for MediaController — Win32 media key control.
"""

import ctypes
from unittest.mock import MagicMock, patch

from src.coordinator.media import MediaController


def test_pause_sends_media_key():
    """Test that pause() sends VK_MEDIA_PLAY_PAUSE key."""
    controller = MediaController()

    with patch("ctypes.windll.user32.SendInput") as mock_send:
        mock_send.return_value = 2  # Success (2 events: key down + key up)

        result = controller.pause()

        assert result is True
        assert mock_send.call_count == 1


def test_pause_handles_sendinput_failure():
    """Test that pause() returns False when SendInput fails."""
    controller = MediaController()

    with patch("ctypes.windll.user32.SendInput") as mock_send:
        mock_send.return_value = 0  # Failure

        result = controller.pause()

        assert result is False
