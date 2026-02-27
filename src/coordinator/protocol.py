"""
Coordination Protocol — Device negotiation for audio handoff.

Devices broadcast their intent scores over UDP (or BLE) and negotiate
which device should hold the active audio connection.
"""

import asyncio
import json
import logging
import socket
import time
import uuid
from dataclasses import dataclass, asdict
from typing import Callable, Optional

from .media import MediaController
from .state import DeviceState, DeviceStateMachine

logger = logging.getLogger(__name__)

# Default coordination port
DEFAULT_PORT = 5555
BROADCAST_INTERVAL = 1.0  # seconds
DEVICE_TIMEOUT = 5.0  # seconds before considering a peer offline
HANDOFF_GRACE_PERIOD = 0.5  # seconds to wait before connecting after winning


@dataclass
class DeviceMessage:
    """Message broadcast by each device in the coordination protocol."""
    device_id: str
    device_name: str
    intent_score: float
    timestamp: float
    audio_state: str  # "playing", "paused", "idle"
    connection_state: str  # "connected", "disconnected", "connecting"
    version: int = 1

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "DeviceMessage":
        parsed = json.loads(data)
        return cls(**parsed)


@dataclass
class PeerDevice:
    """Represents a peer device discovered on the network."""
    device_id: str
    device_name: str
    intent_score: float
    last_seen: float
    audio_state: str
    connection_state: str

    @property
    def is_alive(self) -> bool:
        return (time.time() - self.last_seen) < DEVICE_TIMEOUT


class CoordinationProtocol:
    """
    UDP-based coordination protocol for negotiating audio device handoff.

    Each device broadcasts its intent score periodically. The device with
    the highest score wins the audio connection. Ties are broken by timestamp
    (most recent intent wins).

    Handoff sequence:
        1. Device B detects audio intent → broadcasts high score
        2. Device A (connected) sees B's score > its own
        3. Device A sends YIELD_ACK, gracefully disconnects A2DP
        4. Device B initiates fast reconnect with pre-shared link keys
        5. Audio streams within ~500ms–1.5s
    """

    def __init__(
        self,
        device_name: str,
        port: int = DEFAULT_PORT,
        device_id: Optional[str] = None,
        on_should_connect: Optional[Callable] = None,
        on_should_disconnect: Optional[Callable] = None,
        bluetooth_manager: Optional[object] = None,
    ):
        self.device_id = device_id or str(uuid.uuid4())
        self.device_name = device_name
        self.port = port
        self.peers: dict[str, PeerDevice] = {}
        self.state_machine = DeviceStateMachine()
        self.intent_score: float = 0.0
        self.audio_state: str = "idle"

        # Media control
        self.media_controller = MediaController()

        # Disconnect tracking for debouncing
        self._last_disconnect_time: float = 0.0

        # Callbacks for Bluetooth manager
        self._on_should_connect = on_should_connect
        self._on_should_disconnect = on_should_disconnect

        # Register for unexpected disconnect notifications
        if bluetooth_manager:
            bluetooth_manager._on_disconnect = self._handle_disconnect

        self._sock: Optional[socket.socket] = None
        self._running = False

    def update_intent(self, score: float, audio_state: str = "idle") -> None:
        """Update the local device's intent score and audio state."""
        self.intent_score = score
        self.audio_state = audio_state

        if score > 0 and self.state_machine.state == DeviceState.IDLE:
            self.state_machine.transition(DeviceState.INTENT_DETECTED)
            logger.info(f"Intent detected with score {score}")

        self._evaluate_handoff()

    def _build_message(self) -> DeviceMessage:
        return DeviceMessage(
            device_id=self.device_id,
            device_name=self.device_name,
            intent_score=self.intent_score,
            timestamp=time.time(),
            audio_state=self.audio_state,
            connection_state=self.state_machine.state.value,
        )

    def _evaluate_handoff(self) -> None:
        """
        Determine whether this device should connect or yield
        based on peer intent scores.
        """
        if not self.peers:
            if self.intent_score > 0:
                self._request_connection()
            return

        alive_peers = {k: v for k, v in self.peers.items() if v.is_alive}
        if not alive_peers:
            if self.intent_score > 0:
                self._request_connection()
            return

        max_peer = max(alive_peers.values(), key=lambda p: p.intent_score)

        if self.intent_score > max_peer.intent_score:
            self._request_connection()
        elif self.intent_score < max_peer.intent_score:
            if self.state_machine.state == DeviceState.CONNECTED:
                self._yield_connection()
        else:
            pass  # Tie — most recent timestamp wins

    def _request_connection(self) -> None:
        if self.state_machine.state in (DeviceState.CONNECTED, DeviceState.REQUESTING):
            return
        self.state_machine.transition(DeviceState.REQUESTING)
        logger.info(f"Requesting audio connection (score: {self.intent_score})")
        if self._on_should_connect:
            self._on_should_connect()

    def _yield_connection(self) -> None:
        """
        Coordinated yield to Windows peer.

        Pauses media BEFORE disconnecting to ensure smooth handoff.
        """
        self.state_machine.transition(DeviceState.YIELDING)
        logger.info("Yielding audio connection to higher-priority device")

        # PAUSE, THEN DISCONNECT (in order)
        pause_result = self.media_controller.pause()
        if pause_result:
            logger.debug("Media paused successfully")
        else:
            logger.warning("Failed to pause media, continuing with disconnect")

        if self._on_should_disconnect:
            self._on_should_disconnect()

    def _handle_disconnect(self) -> None:
        """
        Handle unexpected Bluetooth disconnect (iPhone takeover or manual disconnect).

        This is called when Bluetooth disconnects unexpectedly. It pauses media
        and transitions to IDLE state, UNLESS we're in YIELDING state (which
        means the disconnect was expected from coordinated handoff).

        Includes debouncing to prevent rapid disconnect spam.
        """
        # Skip if this is an expected disconnect from coordinated yield
        if self.state_machine.state == DeviceState.YIELDING:
            logger.debug("Disconnect expected (yielding) - skipping pause")
            return

        # Debounce: ignore disconnects within 2 seconds of last one
        now = time.time()
        if now - self._last_disconnect_time < 2.0:
            logger.debug(f"Ignoring rapid disconnect (debounce)")
            return

        self._last_disconnect_time = now

        # Unexpected disconnect - pause and go idle
        logger.info("Bluetooth disconnected - pausing media")
        pause_result = self.media_controller.pause()
        if pause_result:
            logger.debug("Media paused successfully")
        else:
            logger.warning("Failed to pause media on disconnect")

        self.state_machine.transition(DeviceState.IDLE)

    def _handle_peer_message(self, msg: DeviceMessage) -> None:
        """Process a message received from a peer device."""
        if msg.device_id == self.device_id:
            return

        self.peers[msg.device_id] = PeerDevice(
            device_id=msg.device_id,
            device_name=msg.device_name,
            intent_score=msg.intent_score,
            last_seen=time.time(),
            audio_state=msg.audio_state,
            connection_state=msg.connection_state,
        )

        logger.debug(
            f"Peer update: {msg.device_name} "
            f"score={msg.intent_score} state={msg.connection_state}"
        )

        self._evaluate_handoff()

    # ── Async Network Layer ──────────────────────────────────────────

    async def start(self) -> None:
        """Start broadcasting and listening for peer messages."""
        self._running = True

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("", self.port))
        self._sock.setblocking(False)

        logger.info(
            f"Coordination protocol started: {self.device_name} "
            f"({self.device_id[:8]}...) on port {self.port}"
        )

        await asyncio.gather(
            self._broadcast_loop(),
            self._listen_loop(),
            self._cleanup_loop(),
        )

    async def stop(self) -> None:
        """Stop the coordination protocol."""
        self._running = False
        if self._sock:
            self._sock.close()
        logger.info("Coordination protocol stopped")

    async def _broadcast_loop(self) -> None:
        while self._running:
            try:
                msg = self._build_message()
                data = msg.to_json().encode("utf-8")
                self._sock.sendto(data, ("<broadcast>", self.port))
            except Exception as e:
                logger.error(f"Broadcast error: {e}")
            await asyncio.sleep(BROADCAST_INTERVAL)

    async def _listen_loop(self) -> None:
        loop = asyncio.get_event_loop()
        while self._running:
            try:
                data = await loop.sock_recv(self._sock, 4096)
                msg = DeviceMessage.from_json(data.decode("utf-8"))
                self._handle_peer_message(msg)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Invalid message received: {e}")
            except Exception as e:
                logger.error(f"Listen error: {e}")
                await asyncio.sleep(0.1)

    async def _cleanup_loop(self) -> None:
        while self._running:
            stale = [
                pid for pid, peer in self.peers.items() if not peer.is_alive
            ]
            for pid in stale:
                name = self.peers[pid].device_name
                del self.peers[pid]
                logger.info(f"Peer timed out: {name}")
            await asyncio.sleep(DEVICE_TIMEOUT)


# ── CLI Entry Point ──────────────────────────────────────────────────

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Seamless Audio Switch Coordinator")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--name", default=socket.gethostname(), help="Device name")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="UDP port")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    protocol = CoordinationProtocol(
        device_name=args.name,
        port=args.port,
    )

    try:
        await protocol.start()
    except KeyboardInterrupt:
        await protocol.stop()


if __name__ == "__main__":
    asyncio.run(main())
