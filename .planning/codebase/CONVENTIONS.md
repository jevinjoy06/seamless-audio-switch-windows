# Coding Conventions

**Analysis Date:** 2026-02-27

## Naming Patterns

**Files:**
- Snake case with descriptive names: `manager.py`, `protocol.py`, `detector.py`, `signals.py`
- Test files prefixed with `test_`: `test_core.py`, `test_integration.py`, `test_media_controller.py`
- Module-level files grouped by feature domain in subdirectories: `bluetooth/`, `coordinator/`, `intent/`

**Functions:**
- Snake case: `connect()`, `disconnect()`, `get_link_key()`, `start_monitoring()`, `is_device_connected()`
- Private/internal functions prefixed with single underscore: `_handle_peer_message()`, `_evaluate_handoff()`, `_monitor_loop()`
- Helper functions and callbacks use descriptive names: `_handle_should_connect()`, `_handle_disconnect()`, `_check_connection_state()`

**Variables:**
- Snake case for all variables: `target_address`, `device_name`, `intent_score`, `on_disconnect_callback`, `max_peer`
- Private instance variables prefixed with underscore: `_state`, `_monitoring`, `_last_connection_state`, `_connect_start_time`
- Constants use UPPER_SNAKE_CASE: `DEFAULT_PORT`, `BROADCAST_INTERVAL`, `DEVICE_TIMEOUT`, `BT_REGISTRY_PATH`
- Boolean variables use descriptive names: `is_connected`, `_monitoring`, `paired`, `connected`

**Types:**
- Enum classes use PascalCase: `ConnectionState`, `DeviceState`
- Enum values use UPPER_SNAKE_CASE: `DISCONNECTED`, `CONNECTING`, `CONNECTED`, `IDLE`, `INTENT_DETECTED`
- Dataclass names use PascalCase: `BTDevice`, `DeviceMessage`, `PeerDevice`, `SignalReading`, `IntentResult`
- Type hints use standard Python types with lowercase generics: `dict[str, PeerDevice]`, `list[BTDevice]`, `Optional[str]`

## Code Style

**Formatting:**
- No explicit formatter configured (no `.prettierrc` or equivalent found)
- Code follows PEP 8 conventions with clear indentation
- Comments use `#` and are placed above or inline with code
- Docstrings use triple double-quotes (`"""..."""`) for modules, classes, and methods

**Linting:**
- No explicit linter configuration found (no `.eslintrc`, `pyproject.toml`)
- Code appears to follow PEP 8 standards (4-space indentation, 80-100 character line length)
- No obvious style violations in reviewed files

## Import Organization

**Order:**
1. Standard library imports: `import asyncio`, `import json`, `import logging`, `import subprocess`
2. Third-party imports: `from pycaw.pycaw import AudioUtilities`, `import pytest`
3. Local imports: `from src.bluetooth.manager import BluetoothManager`, `from .state import DeviceState`

**Path Aliases:**
- Absolute imports from project root: `from src.bluetooth.manager import BluetoothManager`
- Relative imports within packages: `from .state import DeviceState`, `from .media import MediaController`
- Pattern: Mixed usage depending on context — absolute for cross-module, relative for same-package

## Error Handling

**Patterns:**
- Try-except blocks with specific exception types: `except subprocess.TimeoutExpired:`, `except json.JSONDecodeError:`
- Generic `except Exception as e:` for fallback cases with logging: `logger.error(f"Disconnect error: {e}")`
- No bare `except:` clauses — all exceptions are caught explicitly
- Return `False` for failed operations rather than raising exceptions: `connect()`, `disconnect()` return bool
- Optional return values use `Optional[Type]`: `get_link_key()` returns `Optional[str]`
- State validation before operations: Check `DeviceStateMachine` state before allowing transitions
- Permission errors handled separately: `except PermissionError:` in registry access with informative message

## Logging

**Framework:** Standard Python `logging` module

**Patterns:**
- Logger created per module: `logger = logging.getLogger(__name__)`
- Configured at entry point in `src/main.py` with format string: `"%(asctime)s [%(levelname)s] %(name)s: %(message)s"`
- Log levels used appropriately:
  - `logger.info()` for important state changes: `"Connected to {addr}"`, `"Bluetooth monitoring started"`
  - `logger.warning()` for recoverable issues: `"Connection failed"`, `"Failed to pause media"`
  - `logger.error()` for exceptions: `"Connection error: {e}"`, `"Error reading link key: {e}"`
  - `logger.debug()` for detailed operation flow: `"State: idle → intent_detected"`, `"Peer update: ..."`
- F-strings used for message formatting: `f"Connecting to {addr}..."`
- No custom log handlers in checked files

## Comments

**When to Comment:**
- Comments placed above code sections that explain "why", not "what"
- Section headers use dashes to separate logical blocks: `# ── Component Initialization ────`
- Docstrings document module purpose, class behavior, and method contracts
- Inline comments used sparingly, mostly for complex logic or non-obvious behavior

**JSDoc/TSDoc:**
- Python docstrings (not JSDoc) for all public classes and methods
- Format: Triple-quoted strings immediately after definition
- Include purpose, parameters in function signature, and return type information
- Example from `src/coordinator/protocol.py`:
  ```python
  def _yield_connection(self) -> None:
      """
      Coordinated yield to Windows peer.

      Pauses media BEFORE disconnecting to ensure smooth handoff.
      """
  ```
- Dataclass fields not explicitly documented — rely on class docstring
- No param/return block annotations found (Python 3.10+ style preferred)

## Function Design

**Size:** Functions average 10–30 lines; larger functions broken into logical sections with comments
- `connect()`: 24 lines (includes PowerShell script string)
- `_monitor_loop()`: 8 lines (tight, focused loop)
- `_handle_peer_message()`: 19 lines (clear sequence)

**Parameters:**
- Max 6 parameters typical; use `Optional` for optional args: `def __init__(self, target_address: Optional[str] = None, on_disconnect_callback: Optional[Callable] = None)`
- Type hints on all function parameters and returns: `def connect(self, address: Optional[str] = None) -> bool:`
- Dataclasses used for multi-field returns: `IntentResult`, `DeviceMessage`, `PeerDevice`
- Callback functions passed as optional parameters: `on_should_connect: Optional[Callable]`

**Return Values:**
- Simple types for operations: `bool` for success/failure (`connect()`, `disconnect()`)
- Dataclass instances for complex results: `IntentResult`, `DeviceMessage`
- `Optional[Type]` for values that may not exist: `Optional[str]` for link keys, `Optional[float]` for connection times
- `None` for void operations: `update_intent()`, `start_monitoring()`
- List types explicit: `list[BTDevice]` from `list_paired_devices()`

## Module Design

**Exports:**
- No explicit `__all__` definitions found; all public classes and functions implicitly exported
- Pattern: Public interfaces are the class/function names without leading underscore
- Entry points defined with `if __name__ == "__main__":` pattern in modules with CLI capability

**Barrel Files:**
- `src/bluetooth/__init__.py`, `src/coordinator/__init__.py`, `src/intent/__init__.py` exist but are empty
- Imports done directly from specific modules: `from src.bluetooth.manager import BluetoothManager`
- No re-exports through `__init__.py` — flat explicit imports preferred

---

*Convention analysis: 2026-02-27*
