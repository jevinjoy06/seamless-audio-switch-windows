"""
Link Key Sync — Securely share Bluetooth pairing keys between trusted Windows devices.

This enables any device in the trusted network to connect to the audio device
without re-pairing, replicating Apple's iCloud Keychain behavior.

On Windows, Bluetooth link keys are stored in the Registry at:
    HKLM\\SYSTEM\\CurrentControlSet\\Services\\BTHPORT\\Parameters\\Keys\\<adapter>\\<device>

Security: Keys are encrypted with AES-256-GCM before transmission.
Transport: Keys are synced over the coordination protocol's secure channel.
"""

import hashlib
import json
import logging
import secrets
import winreg
from dataclasses import dataclass, asdict
from typing import Optional

logger = logging.getLogger(__name__)

BT_REGISTRY_PATH = r"SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Keys"


@dataclass
class LinkKeyBundle:
    """A bundle of Bluetooth pairing data for a single device."""
    device_address: str
    device_name: str
    link_key: str
    adapter_address: str
    authenticated: bool = False

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "LinkKeyBundle":
        return cls(**json.loads(data))


class LinkKeyManager:
    """
    Manages extraction and injection of Bluetooth link keys on Windows.

    Extract: Read link keys from the Windows Registry
    Inject: Write link keys to the Windows Registry on another machine
    Sync: Encrypted transfer between trusted devices
    """

    def __init__(self):
        pass

    def extract_key(self, device_address: str) -> Optional[LinkKeyBundle]:
        """
        Extract the link key for a paired device from the Windows Registry.
        Requires administrator privileges.
        """
        addr = device_address.upper().replace(":", "").replace("-", "")

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
                            try:
                                value, reg_type = winreg.QueryValueEx(
                                    adapter_key, addr.lower()
                                )
                                if isinstance(value, bytes):
                                    # Format address back to colon-separated
                                    formatted_addr = ":".join(
                                        addr[j:j + 2] for j in range(0, 12, 2)
                                    )
                                    return LinkKeyBundle(
                                        device_address=formatted_addr,
                                        device_name="",  # Registry doesn't store name here
                                        link_key=value.hex(),
                                        adapter_address=adapter_key_name,
                                    )
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
            logger.error(f"Error extracting link key: {e}")

        return None

    def inject_key(self, bundle: LinkKeyBundle) -> bool:
        """
        Inject a link key into the Windows Registry so this device
        can connect without re-pairing.

        WARNING: This modifies system Bluetooth configuration.
        Requires administrator privileges and a Bluetooth service restart.
        """
        addr = bundle.device_address.replace(":", "").lower()

        try:
            adapter_path = f"{BT_REGISTRY_PATH}\\{bundle.adapter_address}"

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                adapter_path,
                0,
                winreg.KEY_SET_VALUE,
            ) as adapter_key:
                key_bytes = bytes.fromhex(bundle.link_key)
                winreg.SetValueEx(
                    adapter_key, addr, 0, winreg.REG_BINARY, key_bytes
                )

            logger.info(
                f"Injected link key for {bundle.device_address}. "
                "Restart Bluetooth service: "
                "net stop bthserv && net start bthserv"
            )
            return True

        except PermissionError:
            logger.error("Permission denied. Run as Administrator to inject link keys.")
            return False
        except Exception as e:
            logger.error(f"Failed to inject key: {e}")
            return False


# ── Encryption Helpers ───────────────────────────────────────────────

def derive_sync_key(shared_secret: str) -> bytes:
    """
    Derive an encryption key from a shared secret (e.g., account password hash).
    Uses PBKDF2 with a fixed salt for deterministic derivation.
    """
    salt = b"seamless-audio-switch-link-key-sync-v1"
    return hashlib.pbkdf2_hmac("sha256", shared_secret.encode(), salt, 100000)


def encrypt_bundle(bundle: LinkKeyBundle, key: bytes) -> bytes:
    """
    Encrypt a link key bundle using AES-256-GCM.
    Returns: nonce (12 bytes) + ciphertext + tag (16 bytes)
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(12)
    plaintext = bundle.to_json().encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext


def decrypt_bundle(data: bytes, key: bytes) -> LinkKeyBundle:
    """Decrypt a link key bundle."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = data[:12]
    ciphertext = data[12:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return LinkKeyBundle.from_json(plaintext.decode("utf-8"))
