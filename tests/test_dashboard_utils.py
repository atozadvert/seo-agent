import pandas as pd
import unittest

from dashboard_utils import safe_int, safe_float, safe_int_series


class DashboardUtilsTests(unittest.TestCase):
    def test_safe_int_handles_decimal_strings(self):
        self.assertEqual(safe_int("14.6"), 15)
        self.assertEqual(safe_int(None), 0)

    def test_safe_float_handles_decimal_strings(self):
        self.assertEqual(safe_float("14.6"), 14.6)
        self.assertEqual(safe_float(""), 0.0)

    def test_safe_int_series_handles_missing_values(self):
        series = safe_int_series(pd.Series(["14.6", "2", None]))
        self.assertListEqual(series.tolist(), [15, 2, 0])


if __name__ == "__main__":
    unittest.main()
