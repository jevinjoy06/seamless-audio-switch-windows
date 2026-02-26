"""
Bluetooth Manager — Handles BT connections on Windows.

Uses PowerShell + PnP device APIs for Classic Bluetooth (A2DP)
connection management, and the Windows Registry for link key access.
"""

import logging
import subprocess
import time
import winreg
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

# Windows Registry path for Bluetooth link keys
BT_REGISTRY_PATH = r"SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Keys"


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"


@dataclass
class BTDevice:
    """Represents a Bluetooth audio device."""
    address: str
    name: str
    paired: bool = False
    connected: bool = False


class BluetoothManager:
    """
    Manages Bluetooth connections on Windows for seamless audio switching.

    Uses PowerShell + PnP device interfaces for connection control.
    Reads link keys from the Windows Registry for key sync.

    Connection strategy:
        1. Check if device is paired via PnP device enumeration
        2. Toggle connection via Enable/Disable-PnpDevice
        3. Verify connection state
    """

    def __init__(self, target_address: Optional[str] = None):
        self.target_address = target_address
        self._state = ConnectionState.DISCONNECTED
        self._connect_start_time: Optional[float] = None

    @property
    def state(self) -> ConnectionState:
        return self._state

    def connect(self, address: Optional[str] = None) -> bool:
        """
        Connect to a paired Bluetooth audio device.
        Uses PowerShell to enable the Bluetooth PnP device.
        """
        addr = address or self.target_address
        if not addr:
            logger.error("No target device address specified")
            return False

        self._state = ConnectionState.CONNECTING
        self._connect_start_time = time.time()
        logger.info(f"Connecting to {addr}...")

        try:
            ps_script = f'''
            $addr = "{self._format_address(addr)}"
            $device = Get-PnpDevice | Where-Object {{
                $_.FriendlyName -match "Audio" -and
                $_.InstanceId -match ($addr -replace ":", "")
            }} | Select-Object -First 1

            if ($device) {{
                Enable-PnpDevice -InstanceId $device.InstanceId -Confirm:$false
                Write-Output "CONNECTED"
            }} else {{
                Write-Output "DEVICE_NOT_FOUND"
            }}
            '''

            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True, text=True, timeout=15,
            )

            if "CONNECTED" in result.stdout:
                elapsed = time.time() - self._connect_start_time
                self._state = ConnectionState.CONNECTED
                logger.info(f"Connected to {addr} in {elapsed:.2f}s")
                return True
            else:
                self._state = ConnectionState.DISCONNECTED
                logger.warning(f"Connection failed: {result.stdout.strip()}")
                return False

        except subprocess.TimeoutExpired:
            self._state = ConnectionState.DISCONNECTED
            logger.error(f"Connection to {addr} timed out")
            return False
        except Exception as e:
            self._state = ConnectionState.DISCONNECTED
            logger.error(f"Connection error: {e}")
            return False

    def disconnect(self, address: Optional[str] = None) -> bool:
        """Gracefully disconnect from the Bluetooth audio device."""
        addr = address or self.target_address
        if not addr:
            return False

        self._state = ConnectionState.DISCONNECTING
        logger.info(f"Disconnecting from {addr}...")

        try:
            ps_script = f'''
            $addr = "{self._format_address(addr)}"
            $device = Get-PnpDevice | Where-Object {{
                $_.FriendlyName -match "Audio" -and
                $_.InstanceId -match ($addr -replace ":", "")
            }} | Select-Object -First 1

            if ($device) {{
                Disable-PnpDevice -InstanceId $device.InstanceId -Confirm:$false
                Write-Output "DISCONNECTED"
            }}
            '''

            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True, text=True, timeout=10,
            )

            self._state = ConnectionState.DISCONNECTED
            logger.info(f"Disconnected from {addr}")
            return True

        except Exception as e:
            logger.error(f"Disconnect error: {e}")
            self._state = ConnectionState.DISCONNECTED
            return False

    def is_device_connected(self, address: Optional[str] = None) -> bool:
        """Check if a specific Bluetooth device is currently connected."""
        addr = address or self.target_address
        if not addr:
            return False

        try:
            ps_script = f'''
            $addr = "{self._format_address(addr)}"
            $device = Get-PnpDevice -Class Bluetooth | Where-Object {{
                $_.InstanceId -match ($addr -replace ":", "") -and
                $_.Status -eq "OK"
            }}
            if ($device) {{ Write-Output "YES" }} else {{ Write-Output "NO" }}
            '''

            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True, text=True, timeout=5,
            )
            return "YES" in result.stdout

        except Exception:
            return False

    def list_paired_devices(self) -> list[BTDevice]:
        """List all paired Bluetooth devices."""
        devices = []
        try:
            ps_script = '''
            Get-PnpDevice -Class Bluetooth | Where-Object {
                $_.Status -eq "OK" -or $_.Status -eq "Error"
            } | ForEach-Object {
                "$($_.Status)|$($_.InstanceId)|$($_.FriendlyName)"
            }
            '''

            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True, text=True, timeout=10,
            )

            for line in result.stdout.strip().splitlines():
                parts = line.split("|", 2)
                if len(parts) >= 3:
                    status, instance_id, name = parts
                    mac = self._extract_mac_from_instance_id(instance_id)
                    if mac:
                        devices.append(BTDevice(
                            address=mac,
                            name=name.strip(),
                            paired=True,
                            connected=(status.strip() == "OK"),
                        ))

        except Exception as e:
            logger.error(f"Error listing devices: {e}")

        return devices

    def get_link_key(self, address: Optional[str] = None) -> Optional[str]:
        """
        Retrieve the Bluetooth link key from the Windows Registry.

        Keys are stored at:
            HKLM\\SYSTEM\\CurrentControlSet\\Services\\BTHPORT\\Parameters\\Keys\\<adapter>\\<device>

        Requires administrator privileges.
        """
        addr = address or self.target_address
        if not addr:
            return None

        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, BT_REGISTRY_PATH
            ) as keys_root:
                i = 0
                while True:
                    try:
                        adapter_key_name = winreg.EnumKey(keys_root, i)
                        adapter_path = f"{BT_REGISTRY_PATH}\\{adapter_key_name}"

                        with winreg.OpenKey(
                            winreg.HKEY_LOCAL_MACHINE, adapter_path
                        ) as adapter_key:
                            device_reg_name = addr.replace(":", "").lower()
                            try:
                                value, reg_type = winreg.QueryValueEx(
                                    adapter_key, device_reg_name
                                )
                                if isinstance(value, bytes):
                                    return value.hex()
                            except FileNotFoundError:
                                pass

                        i += 1
                    except OSError:
                        break

        except PermissionError:
            logger.error(
                "Permission denied reading Bluetooth registry keys. "
                "Run as Administrator."
            )
        except Exception as e:
            logger.error(f"Error reading link key: {e}")

        return None

    @staticmethod
    def _format_address(address: str) -> str:
        """Normalize a Bluetooth MAC address to colon-separated uppercase."""
        clean = address.replace("-", ":").replace(" ", "").upper()
        if ":" not in clean and len(clean) == 12:
            clean = ":".join(clean[i:i + 2] for i in range(0, 12, 2))
        return clean

    @staticmethod
    def _extract_mac_from_instance_id(instance_id: str) -> Optional[str]:
        """Try to extract a MAC address from a PnP device instance ID."""
        parts = instance_id.upper().split("\\")
        for part in parts:
            clean = part.replace("_", "").replace("-", "")
            if len(clean) == 12 and all(c in "0123456789ABCDEF" for c in clean):
                return ":".join(clean[i:i + 2] for i in range(0, 12, 2))
        return None
