import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.signal_engine import analyze_communication


class SignalEngineTests(unittest.TestCase):
    def test_analyze_communication_flags_hawkish_tone(self):
        text = (
            "Inflation risks remain elevated. The stance remains focused on withdrawal "
            "of accommodation. We will remain vigilant to secure durable alignment with the target."
        )

        result = analyze_communication(text)

        self.assertEqual(result.tone_label, "hawkish")
        self.assertEqual(result.policy_bias, "tightening bias")
        self.assertGreater(result.net_score, 0)
        self.assertGreaterEqual(result.inflation_mentions, 1)
        self.assertGreaterEqual(result.liquidity_mentions, 1)

    def test_analyze_communication_flags_dovish_tone(self):
        text = (
            "Disinflation is broad-based and growth needs support. Space is opening to support "
            "activity as price pressures soften."
        )

        result = analyze_communication(text)

        self.assertEqual(result.tone_label, "dovish")
        self.assertEqual(result.policy_bias, "easing bias")
        self.assertLess(result.net_score, 0)
        self.assertGreaterEqual(result.growth_mentions, 1)

    def test_analyze_communication_treats_balanced_language_as_neutral(self):
        text = (
            "Inflation is easing, but the committee remains vigilant. Growth is steady and "
            "policy will remain data dependent."
        )

        result = analyze_communication(text)

        self.assertEqual(result.tone_label, "neutral")
        self.assertEqual(result.policy_bias, "on hold")


if __name__ == "__main__":
    unittest.main()
