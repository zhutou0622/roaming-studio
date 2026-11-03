import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tap3studio import tapfile  # noqa: E402

BIG = os.environ.get("TAP3_PERF_FILE",
                     r"E:\Deepseek工作目录\Romaing Stadio\CDVGBCCUSAK405097_20240320_135240_POST")


@unittest.skipUnless(os.path.exists(BIG), "large TAP fixture not available")
class TestLargeFilePerformance(unittest.TestCase):
    """Guards the regressions that made big files feel frozen in the UI."""

    @classmethod
    def setUpClass(cls):
        cls.t_open = time.time()
        cls.doc = tapfile.open_document(BIG)
        cls.open_s = time.time() - cls.t_open

    def test_open_time(self):
        self.assertLess(self.open_s, 6.0, f"open took {self.open_s:.2f}s")
        self.assertGreater(len(self.doc.nodes), 100000)

    def test_header_is_cached(self):
        t = time.time()
        for _ in range(100):
            h = self.doc.header()
        self.assertLess(time.time() - t, 0.5)
        self.assertTrue(h["releaseLabel"].startswith("TAP3"))
        self.assertLessEqual(h["tapDecimalPlaces"], 5)

    def test_node_detail_is_shallow(self):
        t = time.time()
        detail = self.doc.node_detail(self.doc.root.node_id)
        self.assertLess(time.time() - t, 0.05)
        self.assertNotIn("children", detail)
        self.assertLess(len(detail["rawHex"]), 400)
        self.assertIn("parent", detail)

    def test_roundtrip_is_byte_identical(self):
        # indefinite-length elements must keep their original form
        self.assertEqual(self.doc.to_bytes(), self.doc.raw)

    def test_save_is_fast(self):
        import tempfile
        path = os.path.join(tempfile.gettempdir(), "tap3studio_perf_roundtrip.tap3")
        t = time.time()
        self.doc.save(path)
        elapsed = time.time() - t
        try:
            self.assertLess(elapsed, 3.0)
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(), self.doc.raw)
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_statistics_and_validation(self):
        t = time.time()
        st = self.doc.statistics()
        self.assertLess(time.time() - t, 1.0)
        self.assertEqual(st["events"], st["auditCount"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
