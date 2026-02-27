# Codebase Structure

**Analysis Date:** 2026-02-27

## Directory Layout

```
seamless-audio-switch-windows/
├── src/                       # Main application code
│   ├── main.py               # Entry point, component wiring, CLI args
│   ├── bluetooth/            # Bluetooth connection management
│   │   ├── __init__.py
│   │   ├── manager.py        # BluetoothManager (connection control, monitoring, registry)
│   │   └── key_sync.py       # Link key encryption (stub, not yet integrated)
│   ├── coordinator/          # Device coordination and media control
│   │   ├── __init__.py
│   │   ├── protocol.py       # CoordinationProtocol (broadcast/listen, handoff logic)
│   │   ├── state.py          # DeviceStateMachine (FSM with IDLE/REQUESTING/CONNECTED/YIELDING states)
│   │   └── media.py          # MediaController (Win32 media key injection)
│   └── intent/               # Intent detection and signal sources
│       ├── __init__.py
│       ├── detector.py       # IntentDetector (weighted score aggregation)
│       └── signals.py        # Signal sources (audio, screen, app focus, interaction)
├── tests/                     # Test suite
│   ├── __init__.py
│   ├── test_core.py          # Unit tests for detector, state machine, media
│   ├── test_integration.py   # Integration tests (all layers)
│   ├── test_bluetooth_manager_monitoring.py  # Bluetooth monitoring thread tests
│   ├── test_coordination_pause.py           # Handoff + pause sequence tests
│   └── test_media_controller.py            # Win32 SendInput tests
├── docs/                      # Documentation (separate from source)
├── config.yaml               # Configuration (device name, coordination params, Bluetooth target)
├── config.example.yaml       # Configuration template
├── requirements.txt          # Python dependencies
├── LICENSE
├── README.md
├── .gitignore
├── .git/
└── .planning/
    └── codebase/             # GSD codebase analysis documents
        ├── ARCHITECTURE.md
        └── STRUCTURE.md
```

## Directory Purposes

**src/:**
- Purpose: Core application code organized by functional layer
- Contains: Python packages for bluetooth, coordinator, intent modules plus main.py entry point
- Key files: `src/main.py` (orchestration), `src/bluetooth/manager.py` (connection control), `src/coordinator/protocol.py` (device negotiation), `src/intent/detector.py` (scoring)

**src/bluetooth/:**
- Purpose: Windows Bluetooth audio device control and monitoring
- Contains: Connection management via PowerShell/PnP, registry link key reading, connection state monitoring thread
- Key files: `src/bluetooth/manager.py` (380 lines), `src/bluetooth/key_sync.py` (stub for encryption)

**src/coordinator/:**
- Purpose: UDP-based device coordination and media control
- Contains: Protocol broadcast/listen loops, state machine, peer device tracking, media pause functionality
- Key files: `src/coordinator/protocol.py` (335 lines), `src/coordinator/state.py` (71 lines), `src/coordinator/media.py` (103 lines)

**src/intent/:**
- Purpose: Detect user intent through multiple OS signal sources
- Contains: Weighted intent scoring, signal implementations for audio/screen/app/interaction detection
- Key files: `src/intent/detector.py` (142 lines), `src/intent/signals.py` (265 lines)

**tests/:**
- Purpose: Pytest test suite covering units, integration, and critical paths
- Contains: Test modules for each layer plus integration tests
- Key files: `tests/test_core.py` (unit tests), `tests/test_integration.py` (full flow), `tests/test_coordination_pause.py` (handoff verification)

**docs/:**
- Purpose: External documentation (separate from this codebase mapping)
- Contains: User guides, API docs (populated externally)

**.planning/codebase/:**
- Purpose: GSD internal analysis documents (not part of source tree)
- Contains: ARCHITECTURE.md, STRUCTURE.md, and other analysis docs written by GSD agents
- Note: Not committed to repo by design; generated on-demand

## Key File Locations

**Entry Points:**
- `src/main.py`: CLI entry point; async main() function that orchestrates all components
- `src/coordinator/protocol.py`: Standalone CLI endpoint with `if __name__ == "__main__"` (unused in main flow)
- `src/intent/detector.py`: Standalone CLI for testing intent scoring

**Configuration:**
- `config.yaml`: Runtime configuration (device name, coordination port/interval, intent weights, Bluetooth target)
- `config.example.yaml`: Template for config.yaml
- `requirements.txt`: Python package dependencies

**Core Logic:**
- `src/bluetooth/manager.py`: Bluetooth connection/disconnection, state monitoring, link key retrieval
- `src/coordinator/protocol.py`: Handoff negotiation, peer tracking, state machine control
- `src/intent/detector.py`: Intent score calculation from weighted signals
- `src/intent/signals.py`: Windows API signal implementations

**Testing:**
- `tests/test_core.py`: Unit tests for detector, state machine, media controller
- `tests/test_integration.py`: End-to-end flow tests
- `tests/test_bluetooth_manager_monitoring.py`: Bluetooth monitoring thread tests
- `tests/test_coordination_pause.py`: Handoff + media pause verification

## Naming Conventions

**Files:**
- Module files: snake_case (e.g., `manager.py`, `detector.py`, `signals.py`)
- Test files: `test_*.py` pattern (e.g., `test_core.py`, `test_integration.py`)
- Config files: lowercase with `.yaml` or `.example.yaml` suffix

**Directories:**
- Package directories: lowercase, singular or plural depending on scope (e.g., `bluetooth`, `coordinator`, `intent`, `tests`)
- No single-letter directories or abbreviations

**Functions:**
- Snake_case throughout (e.g., `start_monitoring()`, `is_device_connected()`, `detect()`)
- Private methods: leading underscore (e.g., `_monitor_loop()`, `_evaluate_handoff()`)
- CLI endpoints: `main()` function

**Classes:**
- PascalCase (e.g., `BluetoothManager`, `CoordinationProtocol`, `IntentDetector`, `DeviceStateMachine`)
- Enum classes: PascalCase (e.g., `DeviceState`, `ConnectionState`)
- Dataclasses: PascalCase (e.g., `IntentResult`, `DeviceMessage`, `PeerDevice`, `BTDevice`)

**Variables:**
- Constants: UPPERCASE_WITH_UNDERSCORES (e.g., `DEFAULT_PORT`, `BROADCAST_INTERVAL`, `VK_MEDIA_PLAY_PAUSE`)
- Instance/local variables: snake_case (e.g., `device_id`, `intent_score`, `is_alive`)

**Imports:**
- Module-level imports: relative within package (e.g., `from .media import MediaController`)
- Standard library first, then third-party, then local

## Where to Add New Code

**New Feature:**
- Primary code: Create new module in appropriate layer (`src/bluetooth/`, `src/coordinator/`, or `src/intent/`)
  - Example: New signal source → add class to `src/intent/signals.py` inheriting from SignalSource
  - Example: New Bluetooth feature → add method to `src/bluetooth/manager.py` or new file in `src/bluetooth/`
- Tests: Add test file in `tests/test_<feature>.py` following existing patterns in `tests/test_core.py`
- Integration: Update `src/main.py` to wire new component if it needs lifecycle management

**New Component/Module:**
- Implementation: Create new directory in `src/<layer>/<component>/` with `__init__.py` and implementation files
- Pattern to follow: Keep modules focused (single responsibility); use dataclasses for data structures; use ABC for interface contracts (see SignalSource)
- Export public API in `__init__.py`

**Utilities/Helpers:**
- Shared helpers: Create `src/utils.py` or `src/common.py` for cross-module utilities
- Layer-specific helpers: Keep in existing module, export via module `__init__.py`
- Windows API wrappers: Group in `src/bluetooth/` or create new `src/windows_api.py` module

## Special Directories

**__pycache__/:**
- Purpose: Compiled Python bytecode cache
- Generated: Yes
- Committed: No (in .gitignore)

**.git/:**
- Purpose: Git version control metadata
- Generated: Yes
- Committed: Yes (always present)

**.pytest_cache/:**
- Purpose: Pytest cache directory
- Generated: Yes (by pytest --cache-dir)
- Committed: No (in .gitignore)

**docs/:**
- Purpose: User-facing documentation
- Generated: No (manually maintained)
- Committed: Yes

**.planning/codebase/:**
- Purpose: GSD internal analysis documents (ARCHITECTURE.md, STRUCTURE.md, etc.)
- Generated: Yes (by GSD agents)
- Committed: No (transient, not part of source tree)

## Module Import Paths

When adding code, use these import patterns:

**From within same package:**
```python
from .state import DeviceStateMachine
from .media import MediaController
```

**From parent package:**
```python
from src.bluetooth.manager import BluetoothManager
from src.intent.detector import IntentDetector
```

**In tests:**
```python
from src.bluetooth.manager import BluetoothManager
from src.coordinator.protocol import CoordinationProtocol
```

Note: Tests import absolutely because pytest adds the project root to sys.path automatically.

## Configuration File Locations

- **Runtime config:** `config.yaml` (user creates from `config.example.yaml`)
- **CLI overrides:** Command-line arguments to `src/main.py` override config.yaml values
- **Environment secrets:** BT_SYNC_SECRET env var (referenced but not enforced in current code)

---

*Structure analysis: 2026-02-27*
