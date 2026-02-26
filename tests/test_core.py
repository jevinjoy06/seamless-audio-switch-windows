"""Tests for the coordination protocol and intent detection."""

import json
import time
import pytest

from src.coordinator.state import DeviceState, DeviceStateMachine
from src.coordinator.protocol import DeviceMessage, CoordinationProtocol
from src.intent.detector import IntentDetector, IntentResult, DEFAULT_WEIGHTS
from src.intent.signals import SignalSource, SignalReading


# ── State Machine Tests ──────────────────────────────────────────────

class TestDeviceStateMachine:
    def test_initial_state_is_idle(self):
        sm = DeviceStateMachine()
        assert sm.state == DeviceState.IDLE

    def test_valid_transition_idle_to_intent(self):
        sm = DeviceStateMachine()
        assert sm.transition(DeviceState.INTENT_DETECTED) is True
        assert sm.state == DeviceState.INTENT_DETECTED

    def test_valid_full_lifecycle(self):
        sm = DeviceStateMachine()
        assert sm.transition(DeviceState.INTENT_DETECTED)
        assert sm.transition(DeviceState.REQUESTING)
        assert sm.transition(DeviceState.CONNECTED)
        assert sm.transition(DeviceState.YIELDING)
        assert sm.transition(DeviceState.IDLE)

    def test_invalid_transition_rejected(self):
        sm = DeviceStateMachine()
        assert sm.transition(DeviceState.CONNECTED) is False
        assert sm.state == DeviceState.IDLE

    def test_is_connected_property(self):
        sm = DeviceStateMachine()
        assert sm.is_connected is False
        sm.transition(DeviceState.INTENT_DETECTED)
        sm.transition(DeviceState.REQUESTING)
        sm.transition(DeviceState.CONNECTED)
        assert sm.is_connected is True

    def test_reset(self):
        sm = DeviceStateMachine()
        sm.transition(DeviceState.INTENT_DETECTED)
        sm.transition(DeviceState.REQUESTING)
        sm.reset()
        assert sm.state == DeviceState.IDLE


# ── Device Message Tests ─────────────────────────────────────────────

class TestDeviceMessage:
    def test_serialization_roundtrip(self):
        msg = DeviceMessage(
            device_id="test-123",
            device_name="test-device",
            intent_score=75.0,
            timestamp=1708900000.0,
            audio_state="playing",
            connection_state="connected",
        )
        json_str = msg.to_json()
        restored = DeviceMessage.from_json(json_str)
        assert restored.device_id == msg.device_id
        assert restored.intent_score == msg.intent_score
        assert restored.audio_state == msg.audio_state


# ── Mock Signal Sources ──────────────────────────────────────────────

class MockSignal(SignalSource):
    def __init__(self, signal_name: str, value: float):
        self._name = signal_name
        self._value = value

    def name(self) -> str:
        return self._name

    def read(self) -> SignalReading:
        return SignalReading(
            source=self._name,
            value=self._value,
            timestamp=time.time(),
        )


# ── Intent Detector Tests ────────────────────────────────────────────

class TestIntentDetector:
    def test_zero_score_when_all_idle(self):
        signals = [
            MockSignal("audio_playing", 0.0),
            MockSignal("device_unlocked", 0.0),
            MockSignal("media_app_foreground", 0.0),
            MockSignal("interaction_recency", 0.0),
        ]
        detector = IntentDetector(signals=signals)
        result = detector.detect()
        assert result.score == 0.0
        assert result.has_intent is False

    def test_max_score_when_all_active(self):
        signals = [
            MockSignal("audio_playing", 1.0),
            MockSignal("device_unlocked", 1.0),
            MockSignal("media_app_foreground", 1.0),
            MockSignal("interaction_recency", 1.0),
        ]
        detector = IntentDetector(signals=signals)
        result = detector.detect()
        assert result.score == 90.0
        assert result.has_intent is True

    def test_audio_playing_dominates(self):
        signals = [
            MockSignal("audio_playing", 1.0),
            MockSignal("device_unlocked", 0.0),
            MockSignal("media_app_foreground", 0.0),
            MockSignal("interaction_recency", 0.0),
        ]
        detector = IntentDetector(signals=signals)
        result = detector.detect()
        assert result.score == 50.0
        assert result.audio_state == "playing"

    def test_custom_weights(self):
        signals = [MockSignal("audio_playing", 1.0)]
        detector = IntentDetector(
            signals=signals,
            weights={"audio_playing": 100},
        )
        result = detector.detect()
        assert result.score == 100.0


# ── Coordination Protocol Tests ──────────────────────────────────────

class TestCoordinationProtocol:
    def test_self_messages_ignored(self):
        protocol = CoordinationProtocol(device_name="test")
        msg = DeviceMessage(
            device_id=protocol.device_id,
            device_name="test",
            intent_score=100.0,
            timestamp=time.time(),
            audio_state="playing",
            connection_state="requesting",
        )
        protocol._handle_peer_message(msg)
        assert len(protocol.peers) == 0

    def test_peer_registered(self):
        protocol = CoordinationProtocol(device_name="test")
        msg = DeviceMessage(
            device_id="peer-123",
            device_name="peer-device",
            intent_score=50.0,
            timestamp=time.time(),
            audio_state="idle",
            connection_state="idle",
        )
        protocol._handle_peer_message(msg)
        assert "peer-123" in protocol.peers
        assert protocol.peers["peer-123"].intent_score == 50.0

    def test_higher_score_triggers_yield(self):
        yielded = []
        protocol = CoordinationProtocol(
            device_name="test",
            on_should_disconnect=lambda: yielded.append(True),
        )
        protocol.state_machine.transition(DeviceState.INTENT_DETECTED)
        protocol.state_machine.transition(DeviceState.REQUESTING)
        protocol.state_machine.transition(DeviceState.CONNECTED)
        protocol.intent_score = 20.0

        msg = DeviceMessage(
            device_id="peer-456",
            device_name="phone",
            intent_score=80.0,
            timestamp=time.time(),
            audio_state="playing",
            connection_state="requesting",
        )
        protocol._handle_peer_message(msg)

        assert len(yielded) == 1
        assert protocol.state_machine.state == DeviceState.YIELDING
