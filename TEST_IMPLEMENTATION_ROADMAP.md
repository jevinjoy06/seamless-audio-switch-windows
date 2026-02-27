# Test Implementation Roadmap

**Priority-based checklist for closing critical test coverage gaps**

---

## CRITICAL: Phase 1 (Before Alpha Release)

### Block 1.1: BluetoothManager Connection Failures (6 tests, Est. 3-4 hours)

- [ ] `test_connect_device_not_found` — PowerShell returns DEVICE_NOT_FOUND
  - File: `tests/test_bluetooth_manager_connections.py` (NEW)
  - Setup: Mock subprocess to return specific PowerShell output
  - Verify: connect() returns False, state = DISCONNECTED
  - Error case: Device MAC address doesn't match any hardware

- [ ] `test_connect_timeout` — PowerShell command exceeds 15s timeout
  - Setup: patch subprocess.run to raise TimeoutExpired
  - Verify: connect() returns False, state = DISCONNECTED
  - Edge case: Timeout during enabling device

- [ ] `test_connect_powershell_exception` — PowerShell execution error
  - Setup: subprocess.run raises OSError
  - Verify: Exception caught, returns False, state = DISCONNECTED
  - Error type: "powershell" not found on PATH

- [ ] `test_connect_while_already_connecting` — Rapid connect calls
  - Setup: Call connect() twice without waiting
  - Verify: Second call returns False or is queued
  - Race condition: State should never be CONNECTING + CONNECTED

- [ ] `test_disconnect_during_monitoring` — Disconnect while monitoring active
  - Setup: start_monitoring() then disconnect()
  - Verify: Monitoring continues, disconnect succeeds
  - Cleanup: No dangling resources

- [ ] `test_monitoring_thread_exception_resilience` — Error in _monitor_loop
  - Setup: Mock _check_connection_state to raise RuntimeError
  - Verify: Thread continues running despite exception
  - Observability: Error logged, monitoring continues

---

### Block 1.2: BluetoothManager Registry/Link Key (5 tests, Est. 3-4 hours)

- [ ] `test_get_link_key_permission_denied` — No admin privileges
  - Setup: Mock winreg.OpenKey to raise PermissionError
  - Verify: get_link_key() returns None
  - Verify: Error logged correctly

- [ ] `test_get_link_key_registry_not_found` — Bluetooth not installed
  - Setup: Mock registry enumeration to raise OSError
  - Verify: get_link_key() returns None
  - Error case: BTHPORT\Parameters\Keys path doesn't exist

- [ ] `test_format_address_edge_cases` — Various MAC address formats
  - Input: "AA:BB:CC:DD:EE:FF" (colon)
  - Input: "AA-BB-CC-DD-EE-FF" (dash)
  - Input: "AABBCCDDEEFF" (no separator)
  - Input: "aa:bb:cc:dd:ee:ff" (lowercase)
  - Verify: All normalize to uppercase with colons

- [ ] `test_extract_mac_from_instance_id_variations` — Instance ID parsing
  - Input: "BTHENUM\{12345678-1234-1234-1234-AABBCCDDEEFF}\0010"
  - Input: "SOME_PATH_AA_BB_CC_DD_EE_FF_OTHER"
  - Input: "No_MAC_Here"
  - Verify: Correctly extracts or returns None

- [ ] `test_list_paired_devices_parsing` — PowerShell output edge cases
  - Input: Empty output (no devices paired)
  - Input: Device with pipe character in name
  - Input: Unusual status values
  - Verify: Graceful parsing, no crashes

---

### Block 1.3: MediaController Exception Paths (5 tests, Est. 2-3 hours)

- [ ] `test_pause_sendInput_partial_success` — Result = 1 (unexpected)
  - Setup: Mock SendInput to return 1 (not 0 or 2)
  - Verify: pause() returns False (conservative)
  - Note: Edge case in Win32 API

- [ ] `test_pause_exception_in_keybdinput_creation` — ctypes exception
  - Setup: Mock KEYBDINPUT to raise exception
  - Verify: pause() returns False, not crash
  - Exception types: TypeError, ValueError, MemoryError

- [ ] `test_pause_exception_in_sendInput_call` — windll.user32 error
  - Setup: Mock ctypes.windll.user32.SendInput to raise AccessDenied
  - Verify: pause() returns False
  - Observability: Error logged

- [ ] `test_pause_none_dwExtraInfo` — NULL pointer handling
  - Setup: Verify KEYBDINPUT.dwExtraInfo = None is valid
  - Verify: pause() succeeds with None pointer
  - Platform check: Windows-specific

- [ ] `test_pause_keyboard_hook_interference` — Hooks block SendInput
  - Setup: Mock SendInput to return 0 (hook blocking)
  - Verify: pause() returns False
  - Note: Indicates Windows security/hook issue

---

### Block 1.4: CoordinationProtocol Network Failures (8 tests, Est. 4-5 hours)

- [ ] `test_start_socket_binding_failure` — Port already in use
  - Setup: patch socket.socket to raise OSError
  - Verify: start() raises or handles gracefully
  - Error case: Port 5555 already bound

- [ ] `test_broadcast_loop_sendto_failure` — Network unreachable
  - Setup: Mock sock.sendto to raise OSError
  - Verify: Loop continues, error logged
  - Observability: No crash, connection remains open

- [ ] `test_listen_loop_oversized_packet` — Packet > 4096 bytes
  - Setup: Mock sock_recv to return 5000-byte packet
  - Verify: Graceful truncation or rejection
  - Buffer overflow check: No segfault

- [ ] `test_listen_loop_binary_garbage` — Non-JSON binary data
  - Setup: Mock sock_recv to return binary garbage
  - Verify: Exception caught (JSONDecodeError)
  - Verify: Peer list unchanged, loop continues

- [ ] `test_listen_loop_incomplete_json` — Partial message
  - Setup: Mock sock_recv to return `b'{"device_id": "test"'` (no closing brace)
  - Verify: JSONDecodeError caught
  - Verify: Loop continues, no peers added

- [ ] `test_listen_loop_malformed_devicemessage` — Invalid field types
  - Setup: from_json receives `{"intent_score": "NaN", ...}`
  - Verify: TypeError or ValueError caught
  - Verify: Message rejected, loop continues

- [ ] `test_cleanup_loop_peer_expiration` — Stale peer removal
  - Setup: Add peer with last_seen in past, wait DEVICE_TIMEOUT
  - Verify: Peer removed from dict
  - Memory check: Dict doesn't grow unbounded

- [ ] `test_protocol_stop_socket_cleanup` — Proper shutdown
  - Setup: start(), then stop()
  - Verify: Socket closed
  - Verify: _running = False, tasks cancelled
  - Resource check: No dangling file descriptors

---

### Block 1.5: CoordinationProtocol Callback Safety (4 tests, Est. 2 hours)

- [ ] `test_yield_connection_callback_exception` — on_should_disconnect raises
  - Setup: on_should_disconnect = lambda: raise RuntimeError()
  - Verify: Exception caught, state = YIELDING
  - Observability: Error logged

- [ ] `test_request_connection_callback_exception` — on_should_connect raises
  - Setup: on_should_connect = lambda: raise RuntimeError()
  - Verify: Exception caught, state = REQUESTING
  - Observability: Error logged

- [ ] `test_handle_disconnect_callback_safe_even_if_paused_fails` — Pause error
  - Setup: pause() raises exception
  - Verify: _handle_disconnect still completes
  - State: Transitions to IDLE even if pause crashes

- [ ] `test_peer_message_handler_exception_resilience` — _handle_peer_message safe
  - Setup: _evaluate_handoff raises exception
  - Verify: Loop continues, peer is still added
  - Observability: Error logged

---

## HIGH: Phase 2 (Before Beta Release)

### Block 2.1: CoordinationProtocol Handoff Logic (6 tests, Est. 3-4 hours)

- [ ] `test_tie_breaking_most_recent_timestamp_wins` — Tie-break logic
  - Device A: score=50, timestamp=100
  - Device B: score=50, timestamp=99
  - Verify: Device with more recent timestamp wins
  - Implementation: Currently `pass` — needs implementation

- [ ] `test_multiple_peers_with_varying_scores` — 3+ peers
  - Peer A: score=60
  - Peer B: score=50
  - Peer C: score=55
  - Device (self): score=50
  - Verify: Yield to highest (Peer A), not just any higher

- [ ] `test_yield_to_peer_then_peer_goes_offline` — Stale peer handling
  - Device CONNECTED → sees peer score higher → YIELDING
  - Peer goes offline (is_alive = False)
  - Verify: Device should reconnect or stay idle?
  - Decision: Define expected behavior

- [ ] `test_intent_score_boundary_equal_scores` — Exact equality
  - score=50.0 vs. peer.score=50.0
  - Verify: Tie-breaking logic applies
  - Edge case: Floating-point precision (50.00001 vs 50.0)

- [ ] `test_score_comparison_with_floating_point_epsilon` — Precision
  - Device score=50.00001, Peer=49.99999
  - Verify: Not treated as tie (use epsilon for comparison?)
  - Decision: Define tolerance

- [ ] `test_request_connection_already_requesting` — Idempotency
  - Device in REQUESTING state
  - Call _request_connection() again
  - Verify: No state corruption, no double callback
  - Design: Should be idempotent

---

### Block 2.2: Intent Detector Signal Failures (8 tests, Est. 4-5 hours)

- [ ] `test_detector_one_signal_fails_others_work` — Partial failure
  - 3 signals return values, 1 raises RuntimeError
  - Verify: Score computed from 3 signals
  - Verify: Failed signal counted as 0.0
  - Behavior: Graceful degradation

- [ ] `test_detector_all_signals_fail` — Complete failure
  - All signals raise RuntimeError
  - Verify: Returns score=0.0
  - Verify: has_intent=False
  - No exceptions raised

- [ ] `test_audio_signal_pycaw_not_installed` — Import error
  - Simulate pycaw not available
  - Verify: Falls back to winmm check
  - Verify: Returns valid SignalReading

- [ ] `test_audio_signal_peak_threshold_boundary` — Peak = 0.01
  - Peak = 0.01 exactly (threshold)
  - Verify: Returns 1.0 (threshold is inclusive >= or >?)
  - Decision: Define boundary behavior

- [ ] `test_media_app_signal_empty_window_title` — No window
  - GetForegroundWindow returns 0
  - Verify: Returns value=0.0
  - No crash

- [ ] `test_media_app_signal_unicode_in_title` — Non-ASCII characters
  - Window title contains emoji: "Spotify 🎵"
  - Verify: Matching still works
  - Encoding: UTF-16 handling correct

- [ ] `test_interaction_recency_tick_count_wraparound` — Overflow
  - Simulate tick count wrap (every 49.7 days)
  - idle_ms becomes negative
  - Verify: max(0.0, ...) handles correctly
  - Result: value = 0.0 (max idle)

- [ ] `test_interaction_recency_just_after_interaction` — Boundary
  - idle_sec = 0.001 (just interacted)
  - Verify: value ≈ 1.0
  - Boundary: Confirm 1.0 - (0.001 / 300) ≈ 1.0

---

### Block 2.3: Main Entry Point Tests (5 tests, Est. 2-3 hours)

- [ ] `test_main_invalid_device_address_format` — Bad MAC
  - Args: --device "INVALID_MAC"
  - Verify: Error message, graceful exit
  - No crash or partial initialization

- [ ] `test_main_missing_required_device_argument` — No device
  - Args: (no --device)
  - Verify: argparse error, usage displayed
  - Exit code: != 0

- [ ] `test_main_bluetooth_connect_failure_doesnt_block_protocol` — Async startup
  - Setup: bt_manager.connect() returns False
  - Verify: protocol.start() still proceeds
  - Behavior: Protocol runs even if BT not connected

- [ ] `test_main_protocol_crash_triggers_cleanup` — Exception in protocol
  - Setup: protocol.start() raises exception
  - Verify: finally block runs
  - Cleanup: bt_manager.stop_monitoring(), protocol.stop()

- [ ] `test_main_keyboard_interrupt_graceful_shutdown` — Ctrl+C
  - Setup: Simulate KeyboardInterrupt
  - Verify: Shutdown message logged
  - Cleanup: All resources released
  - Exit code: 0 (clean exit)

---

### Block 2.4: Signal Source Per-Signal Tests (10 tests, Est. 5-6 hours)

- [ ] `test_audio_playback_signal_exception_in_queryi face` — Interface error
  - QueryInterface raises exception for each session
  - Verify: Returns 0.0 (no audio detected)
  - Graceful: Doesn't crash on one bad session

- [ ] `test_audio_playback_signal_no_active_sessions` — No apps playing
  - GetAllSessions returns empty list
  - Verify: Returns 0.0
  - No IndexError

- [ ] `test_screen_state_signal_locked_desktop` — Workstation locked
  - OpenInputDesktop returns 0 (locked)
  - Verify: Returns 0.0
  - No crash

- [ ] `test_screen_state_signal_openinputdesktop_exception` — Error
  - OpenInputDesktop raises exception
  - Verify: Returns 0.5 (neutral fallback)
  - Observability: Logged as debug

- [ ] `test_media_app_focus_get_foreground_window_null` — No window
  - GetForegroundWindow returns 0
  - Verify: Returns 0.0 (not media app)
  - No null pointer dereference

- [ ] `test_media_app_focus_process_name_extraction_fails` — Process lookup error
  - OpenProcess returns 0
  - Verify: Falls back to empty string
  - Verify: Matching on window title still works

- [ ] `test_media_app_focus_known_app_detection` — Spotify detection
  - Window title = "Spotify"
  - Verify: Returns 1.0
  - Positive: Correctly identifies media app

- [ ] `test_media_app_focus_unknown_app_detection` — Non-media app
  - Window title = "Notepad"
  - Verify: Returns 0.0
  - Negative: Correctly rejects non-media

- [ ] `test_interaction_recency_never_interacted` — Fresh boot
  - Simulate idle_sec = 999999 (very old)
  - Verify: Returns 0.0 (very old interaction)
  - No negative values

- [ ] `test_interaction_recency_max_idle_boundary` — MAX_IDLE = 300
  - idle_sec = 300.0 exactly
  - Verify: Returns 0.0
  - Boundary: Confirm 1.0 - (300 / 300) = 0.0

---

## MEDIUM: Phase 3 (Polish & Hardening)

### Block 3.1: DeviceMessage Validation (5 tests, Est. 2-3 hours)

- [ ] `test_device_message_empty_device_id` — Validation
  - Create with device_id=""
  - Verify: Serializable but questionable
  - Decision: Should reject or allow?

- [ ] `test_device_message_negative_intent_score` — Field validation
  - intent_score = -50.0
  - Verify: Serializable but incorrect
  - Decision: Add schema validation?

- [ ] `test_device_message_missing_required_field` — from_json
  - JSON: `{"device_id": "test"}` (no device_name)
  - Verify: TypeError on from_json()
  - Graceful: Error caught in listen_loop

- [ ] `test_device_message_extra_unknown_fields` — Forward compatibility
  - JSON has "future_field": "value"
  - Verify: Deserialization ignores unknown fields
  - Robustness: Doesn't crash on version=2 messages

- [ ] `test_device_message_oversized_device_name` — Buffer limits
  - device_name = "A" * 10000
  - Verify: Serialization succeeds
  - Check: No buffer overflow when transmitted

---

### Block 3.2: Concurrency & Timing (8 tests, Est. 4-5 hours)

- [ ] `test_bluetooth_monitoring_thread_safety` — Multiple readers
  - start_monitoring(), multiple _check_connection_state calls
  - Verify: No race conditions
  - Thread safety: _last_connection_state protected

- [ ] `test_state_machine_concurrent_transitions` — Race condition
  - Thread A: transition(REQUESTING)
  - Thread B: transition(IDLE)
  - Verify: One wins, state consistent
  - Decision: Add lock or accept race?

- [ ] `test_protocol_rapid_peer_updates` — Message spam
  - Receive 1000 messages in 1 second
  - Verify: No memory leak
  - Verify: _evaluate_handoff called for each

- [ ] `test_disconnect_debounce_backward_clock` — time.time() regression
  - Simulate time.time() goes backward
  - Debounce calculation: 999.5 - 1000.0 < 2.0?
  - Verify: Doesn't trigger extra pause

- [ ] `test_protocol_cleanup_during_broadcast` — Task cancellation
  - Call protocol.stop() while _broadcast_loop running
  - Verify: Socket closed cleanly
  - Resource: No dangling handles

- [ ] `test_bluetooth_stop_monitoring_timeout` — Thread hangs
  - _monitor_loop hangs in is_device_connected()
  - Call stop_monitoring()
  - Verify: join() timeout (2s) expires
  - Behavior: Continues despite timeout

- [ ] `test_intent_detector_signal_timeout` — Slow signal
  - Signal.read() takes 10 seconds
  - detector.detect() called
  - Verify: Blocks or times out?
  - Decision: Define timeout policy

- [ ] `test_coordination_protocol_handoff_race` — CONNECTED → YIELDING race
  - peer_message arrives while in CONNECTED
  - Triggers yield while pause() executing
  - Verify: No state corruption
  - Thread safety: Transitions protected

---

### Block 3.3: Logging & Observability (4 tests, Est. 2 hours)

- [ ] `test_logger_levels_on_error_paths` — Correct severity
  - Verify: pause() failure logs WARNING not ERROR
  - Verify: Configuration error logs ERROR not INFO
  - Consistency: Levels used correctly

- [ ] `test_no_sensitive_data_in_logs` — Privacy
  - Verify: Device ID and MAC logged appropriately
  - No credentials, link keys in logs
  - Audit: Grep for "password", "key" in log output

- [ ] `test_exception_stack_traces_in_logs` — Debugging
  - Verify: Exception.format_exc() included in error logs
  - Not just: logger.error("Failed")
  - Actionability: Stack trace helps debugging

- [ ] `test_performance_timing_logged` — Observability
  - Verify: Connection elapsed time logged
  - Verify: Handoff latency measurable
  - Metrics: Key timings visible in logs

---

### Block 3.4: Resource Cleanup (3 tests, Est. 2 hours)

- [ ] `test_bluetooth_manager_cleanup_on_exception` — Leak prevention
  - connect() raises exception
  - Verify: _monitor_thread not left hanging
  - Verify: Thread can be started again after exception

- [ ] `test_protocol_peer_dict_cleanup` — Memory management
  - Add 1000 peers, let them expire
  - Verify: Dict size decreases
  - No unbounded growth

- [ ] `test_callback_reference_cleanup` — Garbage collection
  - Create protocol, delete it
  - Verify: All callbacks released
  - No circular references preventing GC

---

## Testing Tools & Infrastructure

### Required Pytest Plugins
```bash
pip install pytest pytest-asyncio pytest-cov pytest-timeout
```

### Recommended Test Fixtures (conftest.py)
```python
@pytest.fixture
def mock_windll():
    """Mock ctypes.windll for all tests."""
    with patch('ctypes.windll') as mock:
        yield mock

@pytest.fixture
def mock_subprocess():
    """Mock subprocess for all tests."""
    with patch('subprocess.run') as mock:
        yield mock

@pytest.fixture
def mock_time():
    """Mock time.time() for timing tests."""
    with patch('time.time') as mock:
        mock.return_value = 1000.0
        yield mock
```

### CI/CD Integration
```yaml
# .github/workflows/test.yml
- run: pytest --cov=src --cov-report=xml --cov-report=term
- run: coverage report --fail-under=80
- run: pytest --timeout=5  # Prevent hanging tests
```

---

## Success Criteria

### Phase 1 (CRITICAL) Completion
- [ ] All 28 CRITICAL tests passing
- [ ] BluetoothManager coverage: 60%+
- [ ] CoordinationProtocol coverage: 50%+
- [ ] MediaController coverage: 80%+
- [ ] No known crashes in error paths
- [ ] 0 segfaults/memory leaks

### Phase 2 (HIGH) Completion
- [ ] All 24 HIGH tests passing
- [ ] Intent detector coverage: 70%+
- [ ] Signal sources coverage: 60%+
- [ ] Main entry point coverage: 80%+
- [ ] Handoff logic fully tested
- [ ] Callback safety verified

### Phase 3 (MEDIUM) Completion
- [ ] All 20 MEDIUM tests passing
- [ ] Overall coverage: 75%+
- [ ] Edge cases tested
- [ ] Concurrency verified
- [ ] Resource leaks eliminated
- [ ] Production-ready

---

## Estimated Effort

| Phase | Block Count | Test Count | Hours | Person-Weeks |
|-------|-------------|-----------|-------|--------------|
| **Phase 1** | 5 | 28 | 18-22 | 1.0 |
| **Phase 2** | 4 | 24 | 16-19 | 0.9 |
| **Phase 3** | 4 | 20 | 10-12 | 0.6 |
| **TOTAL** | 13 | **72** | **44-53** | **2.5** |

---

**Generated:** 2026-02-26
**Status:** Ready for implementation planning
