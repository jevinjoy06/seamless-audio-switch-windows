"""
Signal Sources — Windows signal implementations for intent detection.

Uses Win32 APIs (WASAPI, User32, Kernel32) to monitor device state
and determine user intent for audio switching.

Dependencies:
    pip install pycaw comtypes pywin32
"""

import abc
import ctypes
import ctypes.wintypes
import logging
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ── Base Types ───────────────────────────────────────────────────────

@dataclass
class SignalReading:
    """A single reading from a signal source."""
    source: str
    value: float  # 0.0 to 1.0
    timestamp: float
    raw_data: Optional[dict] = None


class SignalSource(abc.ABC):
    """Base class for intent signal sources."""

    @abc.abstractmethod
    def name(self) -> str:
        """Return the signal name (must match a key in the weights dict)."""
        ...

    @abc.abstractmethod
    def read(self) -> SignalReading:
        """Read the current signal value. Returns 0.0–1.0."""
        ...


# ── Win32 Structures ─────────────────────────────────────────────────

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.UINT),
        ("dwTime", ctypes.wintypes.DWORD),
    ]


# ── Audio Detection (WASAPI via pycaw) ───────────────────────────────

class AudioPlaybackSignal(SignalSource):
    """
    Detects active audio playback on Windows using the
    Windows Audio Session API (WASAPI) via pycaw.

    Queries each active audio session and checks if any have
    a non-zero peak meter level (meaning sound is actually playing).
    """

    def name(self) -> str:
        return "audio_playing"

    def read(self) -> SignalReading:
        value = 0.0
        try:
            from pycaw.pycaw import AudioUtilities, IAudioMeterInformation

            sessions = AudioUtilities.GetAllSessions()
            for session in sessions:
                if session.Process:
                    try:
                        meter = session._ctl.QueryInterface(IAudioMeterInformation)
                        peak = meter.GetPeakValue()
                        if peak > 0.01:  # Threshold to ignore silence
                            value = 1.0
                            break
                    except Exception:
                        continue

        except ImportError:
            logger.warning(
                "pycaw not installed. Install with: pip install pycaw comtypes"
            )
            # Fallback: check if any audio output device exists via winmm
            try:
                winmm = ctypes.windll.winmm
                num_devices = winmm.waveOutGetNumDevs()
                value = 0.5 if num_devices > 0 else 0.0
            except Exception:
                value = 0.0
        except Exception as e:
            logger.debug(f"Audio detection error: {e}")

        return SignalReading(
            source=self.name(),
            value=value,
            timestamp=time.time(),
        )


# ── Screen State (User32) ───────────────────────────────────────────

class ScreenStateSignal(SignalSource):
    """
    Detects if the Windows screen is on and the session is unlocked.

    Uses OpenInputDesktop — if the workstation is locked, the call
    returns a null handle.
    """

    def name(self) -> str:
        return "device_unlocked"

    def read(self) -> SignalReading:
        value = 0.0
        try:
            user32 = ctypes.windll.user32
            desk = user32.OpenInputDesktop(0, False, 0x0001)  # DESKTOP_READOBJECTS
            if desk:
                user32.CloseDesktop(desk)
                value = 1.0  # Desktop accessible = unlocked
            else:
                value = 0.0  # Locked
        except Exception as e:
            logger.debug(f"Screen state detection error: {e}")
            value = 0.5  # Unknown — neutral score

        return SignalReading(
            source=self.name(),
            value=value,
            timestamp=time.time(),
        )


# ── Media App Focus (Win32 Window APIs) ──────────────────────────────

class MediaAppFocusSignal(SignalSource):
    """
    Detects if a media application is currently in the foreground.

    Uses GetForegroundWindow + GetWindowText to get the active window
    title and process name, then matches against known media apps.
    """

    MEDIA_APPS = {
        "spotify", "vlc", "groove", "movies & tv", "films & tv",
        "itunes", "amazon music", "youtube", "netflix", "plex",
        "jellyfin", "foobar2000", "winamp", "musicbee",
        "windows media player", "mpv", "potplayer",
        "chrome", "firefox", "edge", "opera", "brave",
    }

    def name(self) -> str:
        return "media_app_foreground"

    def read(self) -> SignalReading:
        value = 0.0
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if hwnd:
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    window_title = buf.value.lower()

                    process_name = self._get_process_name(hwnd)

                    is_media = any(
                        app in window_title or app in process_name
                        for app in self.MEDIA_APPS
                    )
                    value = 1.0 if is_media else 0.0
        except Exception as e:
            logger.debug(f"Media app detection error: {e}")

        return SignalReading(
            source=self.name(),
            value=value,
            timestamp=time.time(),
        )

    @staticmethod
    def _get_process_name(hwnd: int) -> str:
        """Get the process name for a given window handle."""
        try:
            from ctypes import wintypes

            pid = wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

            PROCESS_QUERY_INFORMATION = 0x0400
            PROCESS_VM_READ = 0x0010
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid.value
            )
            if handle:
                buf = ctypes.create_unicode_buffer(260)
                ctypes.windll.psapi.GetModuleBaseNameW(handle, None, buf, 260)
                ctypes.windll.kernel32.CloseHandle(handle)
                return buf.value.lower()
        except Exception:
            pass
        return ""


# ── Interaction Recency (GetLastInputInfo) ───────────────────────────

class InteractionRecencySignal(SignalSource):
    """
    Measures how recently the user interacted with this device.

    Uses GetLastInputInfo from User32 to get the system tick count
    of the last keyboard/mouse input. Score decays linearly from
    1.0 (just interacted) to 0.0 (idle for MAX_IDLE seconds).
    """

    MAX_IDLE = 300  # 5 minutes

    def name(self) -> str:
        return "interaction_recency"

    def read(self) -> SignalReading:
        value = 0.5  # Default neutral
        try:
            lii = LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(LASTINPUTINFO)

            if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
                tick_count = ctypes.windll.kernel32.GetTickCount()
                idle_ms = tick_count - lii.dwTime
                idle_sec = idle_ms / 1000.0
                value = max(0.0, 1.0 - (idle_sec / self.MAX_IDLE))
        except Exception as e:
            logger.debug(f"Interaction recency error: {e}")

        return SignalReading(
            source=self.name(),
            value=value,
            timestamp=time.time(),
        )


# ── Signal Registry ──────────────────────────────────────────────────

ALL_SIGNALS: list[type[SignalSource]] = [
    AudioPlaybackSignal,
    ScreenStateSignal,
    MediaAppFocusSignal,
    InteractionRecencySignal,
]


def get_default_signals() -> list[SignalSource]:
    """Return instances of all available signal sources."""
    return [cls() for cls in ALL_SIGNALS]
