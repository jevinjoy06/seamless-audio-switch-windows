"""
MediaController — Handles media playback control via Windows media keys.

Uses Win32 SendInput API to send VK_MEDIA_PLAY_PAUSE key events,
providing universal media control across all applications.
"""

import ctypes
import logging
from ctypes import Structure, c_long, c_ulong, c_ushort, POINTER, Union

logger = logging.getLogger(__name__)

# Win32 constants
VK_MEDIA_PLAY_PAUSE = 0xB3
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1


# Win32 structures for SendInput
class KEYBDINPUT(Structure):
    _fields_ = [
        ("wVk", c_ushort),         # Virtual key code
        ("wScan", c_ushort),       # Hardware scan code
        ("dwFlags", c_ulong),      # Flags (key down, key up, etc.)
        ("time", c_ulong),         # Timestamp (0 = system provides)
        ("dwExtraInfo", POINTER(c_ulong)),  # Additional info
    ]


class INPUT_UNION(Union):
    _fields_ = [
        ("ki", KEYBDINPUT),
    ]


class INPUT(Structure):
    _fields_ = [
        ("type", c_ulong),         # INPUT_KEYBOARD = 1
        ("union", INPUT_UNION),
    ]


class MediaController:
    """
    Handles media playback control via Windows media keys.

    Uses the Win32 SendInput API to send VK_MEDIA_PLAY_PAUSE key events,
    which works universally across media applications (Spotify, Chrome,
    VLC, Windows Media Player, etc.).
    """

    def pause(self) -> bool:
        """
        Send VK_MEDIA_PLAY_PAUSE key to pause/play media.

        Returns:
            True if the key was sent successfully, False otherwise.

        Note:
            This sends a hardware-level key event that most media applications
            will respond to. It does not guarantee the media was actually paused,
            only that the key event was sent.
        """
        try:
            # Create key down event
            key_down = INPUT()
            key_down.type = INPUT_KEYBOARD
            key_down.union.ki = KEYBDINPUT(
                wVk=VK_MEDIA_PLAY_PAUSE,
                wScan=0,
                dwFlags=KEYEVENTF_EXTENDEDKEY,
                time=0,
                dwExtraInfo=None,
            )

            # Create key up event
            key_up = INPUT()
            key_up.type = INPUT_KEYBOARD
            key_up.union.ki = KEYBDINPUT(
                wVk=VK_MEDIA_PLAY_PAUSE,
                wScan=0,
                dwFlags=KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP,
                time=0,
                dwExtraInfo=None,
            )

            # Send both key down and key up events
            events = (INPUT * 2)(key_down, key_up)
            result = ctypes.windll.user32.SendInput(2, events, ctypes.sizeof(INPUT))

            if result == 2:
                logger.debug("Media pause key sent successfully")
                return True
            else:
                logger.warning(f"SendInput failed: expected 2 events, sent {result}")
                return False

        except Exception as e:
            logger.error(f"Failed to send media pause key: {e}")
            return False
