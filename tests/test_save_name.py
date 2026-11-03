import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tap3studio import generator, tapfile  # noqa: E402

BIG = os.environ.get("TAP3_PERF_FILE",
                     r"E:\Deepseek工作目录\Romaing Stadio\CDVGBCCUSAK405097_20240320_135240_POST")


class TestSaveKeepsName(unittest.TestCase):
    def test_extensionless_file_is_overwritten_in_place(self):
        with tempfile.TemporaryDirectory() as td:
            # a TAP file that carries no extension, like the operator drop files
            name = os.path.join(td, "CDVGBCCUSAK405097_20240320_135240_POST")
            doc = generator.make_document(4, seed=3)
            doc.save(name)
            self.assertTrue(os.path.exists(name))
            self.assertFalse(os.path.exists(name + ".tap3"))

            reopened = tapfile.open_document(name)
            leaf = [n for n in reopened.nodes.values() if n.name == "imsi"][0]
            reopened.set_value(leaf.node_id, "262010000000001")
            reopened.save(name)          # overwrite, byte name unchanged

            self.assertTrue(os.path.exists(name))
            self.assertFalse(os.path.exists(name + ".tap3"))
            again = tapfile.open_document(name)
            self.assertEqual([n.value_text for n in again.nodes.values() if n.name == "imsi"][0],
                             "262010000000001")

    @unittest.skipUnless(os.path.exists(BIG), "large TAP fixture not available")
    def test_large_file_roundtrip_keeps_original_name(self):
        with tempfile.TemporaryDirectory() as td:
            dst = os.path.join(td, os.path.basename(BIG))
            shutil.copyfile(BIG, dst)
            doc = tapfile.open_document(dst)
            doc.save(dst)
            self.assertEqual(os.path.getsize(dst), os.path.getsize(BIG))
            self.assertFalse(os.path.exists(dst + ".tap3"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
