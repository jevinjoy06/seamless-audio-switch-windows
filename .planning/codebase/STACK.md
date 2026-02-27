# Technology Stack

**Analysis Date:** 2026-02-27

## Languages

**Primary:**
- Python 3.10+ - Core application (device coordination, intent detection, Bluetooth management)

## Runtime

**Environment:**
- Windows 10/11 (required for Win32 and Windows Registry APIs)

**Package Manager:**
- pip (CPython standard package manager)
- Lockfile: `requirements.txt` (present)

## Frameworks

**Core:**
- asyncio (built-in) - Asynchronous coordination protocol and event loop management

**Bluetooth & Audio:**
- pycaw 20230407 - Windows Audio Session API (WASAPI) for detecting active audio playback
- pywin32 306 - Win32 API bindings for window enumeration, input simulation, Registry access
- comtypes 1.2 - COM/OLE automation layer for WASAPI audio session interfaces
- cryptography 41.0 - AES-256-GCM encryption for Bluetooth link key synchronization

**Testing:**
- pytest 7.0+ - Unit test runner
- pytest-asyncio 0.21+ - Async test support

**Configuration:**
- PyYAML 6.0+ - YAML config file parsing (`config.yaml`)

## Key Dependencies

**Critical:**
- `pywin32` 306 - Direct access to Windows Registry (Bluetooth link keys), Win32 APIs (media keys, window enumeration, device input simulation). Without it, Bluetooth registry access and media control are impossible on Windows.
- `pycaw` 20230407 - Direct access to Windows Audio Session API for detecting which applications have audio playing. Critical for intent scoring ("audio_playing" signal).
- `comtypes` 1.2 - COM infrastructure for WASAPI interfaces used by pycaw. Dependency of pycaw.
- `cryptography` 41.0 - Encryption for link key synchronization over the network. Implements AES-256-GCM for bundle encryption in `src/bluetooth/key_sync.py`.

**Infrastructure:**
- `pyyaml` 6.0 - Configuration loading from `config.yaml`. Enables device name, Bluetooth target, intent weights, coordination port customization.

## Windows Platform APIs (via ctypes & pywin32)

**Registry (winreg):**
- HKLM\SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Keys - Read/write Bluetooth link keys
- Used by: `src/bluetooth/manager.py` (get_link_key), `src/bluetooth/key_sync.py` (extract_key, inject_key)

**Win32 Kernel (kernel32):**
- GetTickCount - Get system tick count for idle time calculation
- OpenProcess, GetModuleBaseNameW - Get process names from window handles
- CloseHandle - Resource cleanup

**Win32 User (user32):**
- GetForegroundWindow, GetWindowTextW - Get active window title
- GetWindowThreadProcessId - Get PID of foreground window
- SendInput - Send media key events (VK_MEDIA_PLAY_PAUSE) for play/pause
- GetLastInputInfo - Detect user interaction recency
- OpenInputDesktop, CloseDesktop - Detect if Windows is locked

**Process API (psapi):**
- GetModuleBaseNameW - Get executable name from process handle

**Subprocess (PowerShell):**
- powershell.exe with Get-PnpDevice, Enable-PnpDevice, Disable-PnpDevice - Connect/disconnect Bluetooth audio devices (requires admin)

## Configuration

**Environment:**
- `config.yaml` - Device name, Bluetooth target MAC, UDP coordination port, intent weights, logging level
- Example: `config.example.yaml`
- Environment variables: BT_SYNC_SECRET (optional, for link key encryption salt)

**Build:**
- No build system (pure Python, runs directly)
- Entry point: `python -m src.main --device AA:BB:CC:DD:EE:FF --name my-laptop --port 5555`

## Platform Requirements

**Development:**
- Windows 10/11 (all Win32 API calls are Windows-only)
- Administrator privileges (required for Registry access and Bluetooth device control)
- Python 3.10+
- PowerShell (for Bluetooth PnP device enumeration and control)
- Bluetooth hardware and driver support

**Production:**
- Windows 10/11 (no cross-platform compatibility)
- Administrator privileges (Registry and device control)
- Bluetooth Multipoint audio device paired on the system
- Network connectivity (UDP on port 5555 by default for inter-device coordination)

---

*Stack analysis: 2026-02-27*
