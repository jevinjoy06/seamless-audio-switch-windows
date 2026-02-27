"""
Main entry point for Seamless Audio Switch.

Wires together all components:
- IntentDetector → measures device intent score
- CoordinationProtocol → negotiates device handoff
- BluetoothManager → manages Bluetooth connection
- MediaController → pauses media on handoff
"""

import argparse
import asyncio
import logging
import socket
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.bluetooth.manager import BluetoothManager
from src.coordinator.protocol import CoordinationProtocol

logger = logging.getLogger(__name__)


async def main():
    """Main application entry point."""
    parser = argparse.ArgumentParser(
        description="Seamless Audio Switch - Windows Smart Yield"
    )
    parser.add_argument(
        "--device",
        required=True,
        help="Target Bluetooth device MAC address (e.g., AA:BB:CC:DD:EE:FF)"
    )
    parser.add_argument(
        "--name",
        default=socket.gethostname(),
        help="This device's name for coordination"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5555,
        help="UDP port for coordination protocol"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    logger.info("=" * 60)
    logger.info("Seamless Audio Switch - Windows Smart Yield")
    logger.info("=" * 60)
    logger.info(f"Device: {args.device}")
    logger.info(f"Name: {args.name}")
    logger.info(f"Port: {args.port}")

    # ── Component Initialization ──────────────────────────────────

    # 1. Create BluetoothManager
    bt_manager = BluetoothManager(target_address=args.device)

    # 2. Create CoordinationProtocol with callbacks
    protocol = CoordinationProtocol(
        device_name=args.name,
        port=args.port,
        on_should_connect=lambda: _handle_should_connect(bt_manager),
        on_should_disconnect=lambda: _handle_should_disconnect(bt_manager),
        bluetooth_manager=bt_manager  # Registers disconnect callback
    )

    # 3. Start Bluetooth connection monitoring
    bt_manager.start_monitoring()
    logger.info("Bluetooth monitoring started")

    # 4. Start coordination protocol
    logger.info("Starting coordination protocol...")

    try:
        await protocol.start()
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
    finally:
        # Clean shutdown
        bt_manager.stop_monitoring()
        await protocol.stop()
        logger.info("Shutdown complete")


def _handle_should_connect(bt_manager: BluetoothManager) -> None:
    """Callback when this device should connect to Bluetooth."""
    logger.info("Attempting to connect to Bluetooth device...")
    success = bt_manager.connect()
    if success:
        logger.info("✓ Bluetooth connected successfully")
    else:
        logger.warning("✗ Bluetooth connection failed")


def _handle_should_disconnect(bt_manager: BluetoothManager) -> None:
    """Callback when this device should disconnect Bluetooth."""
    logger.info("Disconnecting from Bluetooth device...")
    success = bt_manager.disconnect()
    if success:
        logger.info("✓ Bluetooth disconnected successfully")
    else:
        logger.warning("✗ Bluetooth disconnect failed")


if __name__ == "__main__":
    asyncio.run(main())
