# Codebase Concerns

**Analysis Date:** 2026-02-27

## Tech Debt

**PowerShell Subprocess Hardcoding:**
- Issue: Connection/disconnection logic relies on inline PowerShell scripts passed to `subprocess.run()` with no parameterization or injection protection
- Files: `src/bluetooth/manager.py` (lines 86-99, 135-146, 169-176, 191-197)
- Impact: Scripts are difficult to test, maintain, and audit. If device addresses contain special characters or quotes, parsing could fail silently
- Fix approach: Extract PowerShell scripts to external `.ps1` files or use proper parameter binding in Get-PnpDevice queries. Validate all address inputs before interpolation

**Network Security - UDP Broadcast Without Authentication:**
- Issue: CoordinationProtocol broadcasts device intent scores via UDP broadcast with no authentication or encryption
- Files: `src/coordinator/protocol.py` (lines 272-280, 248-251)
- Impact: Any device on the local network can impersonate a peer and trigger false handoffs. Link key sync comments mention AES-256-GCM but encryption is not implemented in the broadcast loop
- Fix approach: Implement HMAC-SHA256 message authentication, require device discovery/pairing before accepting peer messages, or use BLE transport instead of UDP

**Synchronous Registry Access on Network Operations:**
- Issue: `get_link_key()` in `BluetoothManager` reads Windows Registry synchronously during connection attempts, which may block the main thread
- Files: `src/bluetooth/manager.py` (lines 222-270)
- Impact: Large registry enumeration (lines 239-260 loop) could hang connection attempts for 1-2 seconds
- Fix approach: Move registry access to a thread pool executor or cache link keys at startup

**Bare Exception Handlers Without Logging Context:**
- Issue: Multiple except blocks catch generic `Exception` but don't provide sufficient context for debugging (lines 120, 157, 308)
- Files: `src/bluetooth/manager.py`, `src/coordinator/protocol.py`, `src/intent/signals.py`
- Impact: When PowerShell scripts fail (e.g., due to permission issues), error messages are generic and don't include stderr output
- Fix approach: Capture `result.stderr` and include it in error logging; use specific exception types where possible

**Timing-Dependent State Transitions:**
- Issue: `_check_connection_state()` polls every 1 second, but connection/disconnection may take 2-3 seconds. State transitions can race with actual device state
- Files: `src/bluetooth/manager.py` (line 311), `src/coordinator/protocol.py` (line 203-209)
- Impact: Disconnect callback may be delayed or missed if device state changes faster than polling interval
- Fix approach: Use Windows device change notifications (WM_DEVICECHANGE) instead of polling, or reduce polling interval to 0.1-0.5 seconds

## Known Bugs

**Lost Connection During Coordinated Yield:**
- Symptoms: If Bluetooth disconnects between the YIELDING state and _on_should_disconnect() callback, media is not paused and device goes silent
- Files: `src/coordinator/protocol.py` (lines 169-186, 199-201)
- Trigger: Bluetooth drops during the pause() call in _yield_connection()
- Workaround: Monitor logs for "Yielding..." messages followed by unexpected disconnect; manually reconnect

**Media Pause Key Not Reliable Across All Applications:**
- Symptoms: Some applications (especially browser-based audio) don't respond to VK_MEDIA_PLAY_PAUSE key events
- Files: `src/coordinator/media.py` (lines 54-102)
- Trigger: Playback on YouTube, Twitch, or Slack audio
- Workaround: Comment states "does not guarantee the media was actually paused, only that the key event was sent" — requires manual pause

**Registry Path Iteration May Skip Adapters:**
- Symptoms: `get_link_key()` and `extract_key()` enumerate registry keys but may not find the correct adapter if multiple Bluetooth adapters exist
- Files: `src/bluetooth/manager.py` (lines 239-260), `src/bluetooth/key_sync.py` (lines 68-96)
- Trigger: Devices with multiple Bluetooth adapters (USB dongle + built-in)
- Workaround: Manually look up adapter address in Device Manager and ensure target device is paired on the primary adapter

**Debounce Logic Allows Rapid Reconnects:**
- Symptoms: If Bluetooth disconnect-reconnect happens within 2 seconds, the debounce check (line 205) prevents pause-on-disconnect, leaving media playing
- Files: `src/coordinator/protocol.py` (lines 203-207)
- Trigger: Unstable Bluetooth connection or rapid manual connect/disconnect cycles
- Workaround: None — media will continue playing until manually paused

## Security Considerations

**Registry Read Requires Admin Privileges:**
- Risk: `get_link_key()` fails silently if not run as Administrator. Users won't know pairing is not synced
- Files: `src/bluetooth/manager.py` (lines 262-266), `src/bluetooth/key_sync.py` (lines 98-102)
- Current mitigation: Error is logged, but application continues anyway
- Recommendations:
  1. Check admin rights at startup and warn prominently
  2. Provide elevated prompt on Windows if available
  3. Document "Run as Administrator" requirement clearly

**Link Key Material Transmitted Over Plaintext UDP:**
- Risk: If link key sync is implemented via CoordinationProtocol, keys are broadcast unencrypted (see `key_sync.py` header comments)
- Files: `src/bluetooth/key_sync.py` (lines 10-11 suggest intent but implementation incomplete), `src/coordinator/protocol.py` (no key transmission code yet)
- Current mitigation: Key sync not yet integrated into protocol
- Recommendations:
  1. Only enable key sync over TLS/mTLS, not UDP
  2. Implement pre-shared secrets and HMAC authentication
  3. Test with MITM tools before production use

**Command Injection Risk in PowerShell:**
- Risk: Device addresses are interpolated directly into PowerShell scripts (line 87, 136, 170, 194)
- Files: `src/bluetooth/manager.py` (all PowerShell script blocks)
- Current mitigation: Addresses are validated in `_format_address()` but validation is only whitelist-by-length, not by character class
- Recommendations:
  1. Use parameterized PowerShell (no string interpolation)
  2. Validate addresses against regex: `^([0-9A-Fa-f]{2}:){5}([0-9A-Fa-f]{2})$`
  3. Use `subprocess` with `shell=False` where possible

**Process Handle Leak in Signal Detection:**
- Risk: `_get_process_name()` opens process handle without guaranteed close in all exception paths
- Files: `src/intent/signals.py` (lines 192-212)
- Current mitigation: CloseHandle is called in normal path (line 208)
- Recommendations:
  1. Use try-finally to guarantee handle closure
  2. Consider using `wmi.WMI()` instead of raw Win32 APIs

## Performance Bottlenecks

**UDP Broadcast Every 1 Second Across All Peers:**
- Problem: CoordinationProtocol broadcasts on every peer update, creating network traffic even when intent score hasn't changed
- Files: `src/coordinator/protocol.py` (lines 272-280)
- Cause: BROADCAST_INTERVAL (1.0s) is fixed; messages are always sent regardless of score changes
- Improvement path:
  1. Only broadcast when intent_score changes by >5.0 points
  2. Implement exponential backoff for idle devices
  3. Use multicast instead of broadcast to reduce network noise

**Synchronous Signal Reading Blocks Intent Detection:**
- Problem: `detect()` waits for all signal sources to complete before returning. If one signal hangs, entire detection loop stalls
- Files: `src/intent/detector.py` (lines 78-87)
- Cause: Signals read audio, screen, window state, and interaction sequentially
- Improvement path:
  1. Run signal reads in parallel with `asyncio.gather()` or `ThreadPoolExecutor`
  2. Set per-signal timeouts (e.g., 100ms max)
  3. Cache recent readings and return stale data if current read times out

**Registry Enumeration O(n) Per Connection Attempt:**
- Problem: `get_link_key()` iterates through ALL adapters and ALL their device keys to find target device
- Files: `src/bluetooth/manager.py` (lines 239-260)
- Cause: No index or direct path lookup available in Windows Registry
- Improvement path:
  1. Cache adapter addresses at startup
  2. Try target adapter first, fall back to enumeration
  3. Build and cache a lookup table on first run

## Fragile Areas

**CoordinationProtocol State Machine Lacks Race Condition Handling:**
- Files: `src/coordinator/protocol.py` (lines 151-159)
- Why fragile: Multiple async tasks (_broadcast_loop, _listen_loop) can call `_evaluate_handoff()` concurrently, causing non-atomic state transitions
- Safe modification: Add a lock around state machine transitions; consider using `asyncio.Lock` to serialize evaluation
- Test coverage: No tests for concurrent peer updates; tests are synchronous

**Media Pause Timing Dependency:**
- Files: `src/coordinator/protocol.py` (lines 178-186)
- Why fragile: `pause()` returns immediately (doesn't wait for playback to actually stop). `disconnect()` may be called before pause takes effect
- Safe modification: Add 100-200ms delay between pause and disconnect; implement pause confirmation
- Test coverage: `test_yield_connection_pauses_before_disconnect` only verifies call order, not actual timing

**BluetoothManager Connection State Inconsistent With Actual Device State:**
- Files: `src/bluetooth/manager.py` (lines 58-65, 81-123)
- Why fragile: `_state` is set to CONNECTED immediately after Enable-PnpDevice call, but device may take 1-2s to actually connect
- Safe modification: Poll `is_device_connected()` in a loop before setting state to CONNECTED; add connection timeout
- Test coverage: No integration tests with actual Bluetooth hardware; all tests are mocked

**Signal Reading Exceptions Silently Fail to Neutral Score:**
- Files: `src/intent/detector.py` (lines 85-87)
- Why fragile: If a signal fails, it scores 0.0 but exception is only logged at WARNING level. Caller doesn't know detection is degraded
- Safe modification: Return degraded flag in IntentResult; track which signals are failing; alert on repeated failures
- Test coverage: No tests for signal failures; only happy path tested

## Scaling Limits

**UDP Broadcast Limited to Local Network:**
- Current capacity: Works reliably with 5-10 devices on same LAN
- Limit: Breaks when devices span multiple subnets or use VPN/roaming
- Scaling path:
  1. Implement relay server for cross-network coordination
  2. Add optional cloud signaling (e.g., MQTT broker)
  3. Support mDNS discovery instead of UDP broadcast

**Threading Model Not Scalable to Many Devices:**
- Current capacity: Each monitoring task creates one daemon thread
- Limit: With 100+ monitoring instances, thread overhead becomes significant
- Scaling path:
  1. Use `select.select()` or `asyncio` for all I/O instead of threads
  2. Merge monitoring into single async event loop
  3. Profile context switch overhead on large deployments

**Registry Enumeration Doesn't Scale to Many Devices:**
- Current capacity: Fast for 1-3 paired Bluetooth devices
- Limit: Slow enumeration (100+ adapters/devices) blocks connection requests
- Scaling path:
  1. Cache adapter/device mappings at startup
  2. Implement WMI query instead of registry enumeration
  3. Use Windows Bluetooth APIs directly (BluetoothFindDeviceClose, etc.)

## Dependencies at Risk

**pycaw Audio Detection Fragile Across Windows Versions:**
- Risk: pycaw uses COM interfaces that changed significantly between Windows 10 and Windows 11
- Impact: Audio playback detection (AudioPlaybackSignal) may fail on some builds
- Migration plan: Implement fallback using `winmm.waveOutGetNumDevs()` (already present at lines 93-95); consider migrating to new WASAPI Rust bindings if maintained

**pywin32 Requires Post-Install Script:**
- Risk: `pywin32 >= 306` requires running `python Scripts/pywin32_postinstall.py` after pip install, otherwise COM calls fail
- Impact: Silent failures in CI/CD or user installations if post-install is skipped
- Migration plan: Add post-install hook to setup.py; document in README; consider vendoring critical Windows API calls

**cryptography Library Import Only When Needed:**
- Risk: `encrypt_bundle()` and `decrypt_bundle()` import `cryptography.hazmat.primitives` inside functions (lines 163, 173)
- Impact: ImportError only occurs at runtime when key sync is called, not at startup
- Migration plan: Move imports to module level; fail fast at startup if dependencies missing

## Missing Critical Features

**No Link Key Sync Implementation:**
- Problem: `key_sync.py` defines encryption but no integration with CoordinationProtocol; link key sharing not connected to actual handoff
- Blocks: Cross-device seamless pairing (requires manual pairing on each device)
- Files: `src/bluetooth/key_sync.py` (standalone, unused)

**No Configuration File Loading:**
- Problem: `config.yaml` exists but is never loaded; all settings are hardcoded (e.g., port 5555, broadcast interval 1.0)
- Blocks: User customization without code changes
- Files: `config.yaml` (ignored), `src/main.py` (no config loading)

**No Persistent Device Pairing State:**
- Problem: No JSON/SQLite database of trusted devices; peer discovery is stateless and ephemeral
- Blocks: Offline operation and cross-session device memory
- Files: `src/coordinator/protocol.py` (peers dict lives only in memory)

## Test Coverage Gaps

**BluetoothManager PowerShell Integration Untested:**
- What's not tested: Actual PowerShell execution, MAC address parsing from instance IDs, Windows Registry reading
- Files: `src/bluetooth/manager.py` (all PowerShell interaction, registry calls)
- Risk: Bug in string interpolation, timeout handling, or PowerShell parsing only discovered in production
- Priority: **High** — connection is critical path

**CoordinationProtocol Network Layer Untested:**
- What's not tested: UDP socket creation, broadcast send/receive, deserialization of malformed JSON
- Files: `src/coordinator/protocol.py` (lines 244-305)
- Risk: Network errors, dropped packets, or malicious messages not handled gracefully
- Priority: **High** — network is critical for device negotiation

**Signal Sources on Real Windows Systems Untested:**
- What's not tested: Actual audio detection via pycaw, screen lock detection, window focus detection, process name retrieval
- Files: `src/intent/signals.py` (all signal sources except in test mocks)
- Risk: Silent failures if Win32 APIs are unavailable or behavior differs across Windows versions
- Priority: **Medium** — graceful fallback exists but intent detection would be degraded

**MediaController SendInput on Real Applications Untested:**
- What's not tested: Actual media key delivery to Spotify, Chrome, VLC, or other applications
- Files: `src/coordinator/media.py` (pause implementation)
- Risk: Key may not be received or understood by all media applications
- Priority: **Medium** — workaround is manual pause

**Integration Between Modules Untested:**
- What's not tested: BluetoothManager disconnect callback triggering protocol state machine transitions during active coordination
- Files: `src/main.py` (wiring), `src/coordinator/protocol.py` (callback registration)
- Risk: Race condition between expected disconnect (coordinated yield) and unexpected disconnect (user action)
- Priority: **Medium** — race conditions hard to reproduce but happen in field

**Error Path Recovery Untested:**
- What's not tested: Reconnection after failed connection, state recovery after socket error, media pause failure with continued disconnect
- Files: All files with `except` blocks
- Risk: Application gets stuck in REQUESTING or YIELDING state after transient failure
- Priority: **Medium** — graceful recovery is expected

---

*Concerns audit: 2026-02-27*
