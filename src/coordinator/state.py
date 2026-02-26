"""
Device State Machine — Tracks the connection lifecycle of a device.

States:
    IDLE → INTENT_DETECTED → REQUESTING → CONNECTED → YIELDING → IDLE
"""

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class DeviceState(Enum):
    IDLE = "idle"
    INTENT_DETECTED = "intent_detected"
    REQUESTING = "requesting"
    CONNECTED = "connected"
    YIELDING = "yielding"


# Valid state transitions
TRANSITIONS = {
    DeviceState.IDLE: {DeviceState.INTENT_DETECTED},
    DeviceState.INTENT_DETECTED: {DeviceState.REQUESTING, DeviceState.IDLE},
    DeviceState.REQUESTING: {DeviceState.CONNECTED, DeviceState.IDLE, DeviceState.YIELDING},
    DeviceState.CONNECTED: {DeviceState.YIELDING, DeviceState.IDLE},
    DeviceState.YIELDING: {DeviceState.IDLE},
}


class DeviceStateMachine:
    """Finite state machine for device connection lifecycle."""

    def __init__(self):
        self._state = DeviceState.IDLE
        self._history: list[tuple[DeviceState, DeviceState]] = []

    @property
    def state(self) -> DeviceState:
        return self._state

    def transition(self, new_state: DeviceState) -> bool:
        """
        Attempt a state transition. Returns True if successful.
        Invalid transitions are logged and rejected.
        """
        if new_state not in TRANSITIONS.get(self._state, set()):
            logger.warning(
                f"Invalid transition: {self._state.value} → {new_state.value}"
            )
            return False

        old_state = self._state
        self._state = new_state
        self._history.append((old_state, new_state))
        logger.debug(f"State: {old_state.value} → {new_state.value}")
        return True

    def reset(self) -> None:
        """Reset to IDLE state."""
        self._state = DeviceState.IDLE

    @property
    def is_connected(self) -> bool:
        return self._state == DeviceState.CONNECTED

    @property
    def is_active(self) -> bool:
        return self._state not in (DeviceState.IDLE,)
