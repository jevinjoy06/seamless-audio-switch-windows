"""
Intent Detector — Computes a composite intent score from multiple signal sources.

The intent score determines how strongly this device "wants" the audio connection.

Score formula:
    score = Σ (signal_value × weight)

Default weights:
    audio_playing:          50
    device_unlocked:        20
    media_app_foreground:   15
    device_picked_up:       10  (mobile only)
    interaction_recency:     5
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

from .signals import SignalSource, SignalReading, get_default_signals

logger = logging.getLogger(__name__)

# Default intent weights
DEFAULT_WEIGHTS = {
    "audio_playing": 50,
    "device_unlocked": 20,
    "media_app_foreground": 15,
    "device_picked_up": 10,
    "interaction_recency": 5,
}


@dataclass
class IntentResult:
    """Result of an intent detection cycle."""
    score: float
    signals: dict[str, float]
    audio_state: str
    timestamp: float

    @property
    def has_intent(self) -> bool:
        """Returns True if the score indicates meaningful intent."""
        return self.score > 10.0


class IntentDetector:
    """
    Computes a weighted intent score from multiple device signals.

    Usage:
        detector = IntentDetector()
        result = detector.detect()
        print(f"Intent score: {result.score}")
    """

    def __init__(
        self,
        weights: Optional[dict[str, float]] = None,
        signals: Optional[list[SignalSource]] = None,
        poll_interval: float = 0.5,
    ):
        self.weights = weights or DEFAULT_WEIGHTS.copy()
        self.signals = signals or get_default_signals()
        self.poll_interval = poll_interval
        self._last_result: Optional[IntentResult] = None

    def detect(self) -> IntentResult:
        """
        Run all signal sources and compute the composite intent score.
        """
        readings: dict[str, float] = {}
        audio_state = "idle"

        for signal in self.signals:
            try:
                reading = signal.read()
                readings[reading.source] = reading.value

                if reading.source == "audio_playing" and reading.value > 0:
                    audio_state = "playing"
            except Exception as e:
                logger.warning(f"Signal {signal.name()} failed: {e}")
                readings[signal.name()] = 0.0

        # Compute weighted score
        score = sum(
            readings.get(name, 0.0) * weight
            for name, weight in self.weights.items()
        )

        result = IntentResult(
            score=score,
            signals=readings,
            audio_state=audio_state,
            timestamp=time.time(),
        )

        self._last_result = result
        return result

    @property
    def last_result(self) -> Optional[IntentResult]:
        return self._last_result


# ── CLI Entry Point ──────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Intent Detection Service")
    parser.add_argument("--interval", type=float, default=1.0, help="Poll interval (s)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO
    )

    detector = IntentDetector(poll_interval=args.interval)

    print("Intent Detector running. Press Ctrl+C to stop.\n")
    try:
        while True:
            result = detector.detect()
            print(
                f"Score: {result.score:5.1f} | "
                f"Audio: {result.audio_state:7s} | "
                f"Signals: {result.signals}"
            )
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
