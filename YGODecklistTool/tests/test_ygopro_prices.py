import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from pricing.ygopro_prices import parse_cardmarket_price


class TestYGOPRODeckPriceParsing(unittest.TestCase):
    def test_parse_cardmarket_price_valid(self) -> None:
        self.assertEqual(parse_cardmarket_price("12.34"), 12.34)
        self.assertEqual(parse_cardmarket_price("0"), 0.0)

    def test_parse_cardmarket_price_invalid(self) -> None:
        self.assertIsNone(parse_cardmarket_price(None))
        self.assertIsNone(parse_cardmarket_price("not-a-number"))


if __name__ == "__main__":
    unittest.main()
