import unittest
from datetime import date, datetime

from app.time_utils import APPLICATION_TIMEZONE_NAME, now_local, today_local


class ShanghaiTimeUtilsTest(unittest.TestCase):
    def test_application_timezone_is_explicit(self):
        self.assertEqual(APPLICATION_TIMEZONE_NAME, "Asia/Shanghai")

    def test_now_local_is_naive_but_matches_shanghai_clock(self):
        current = now_local()
        self.assertIsInstance(current, datetime)
        self.assertIsNone(current.tzinfo)
        self.assertEqual(current.date(), today_local())

    def test_today_local_returns_a_date(self):
        self.assertIsInstance(today_local(), date)


if __name__ == "__main__":
    unittest.main()
