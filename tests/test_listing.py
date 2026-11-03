import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tap3studio import generator, ops, tapfile  # noqa: E402


class TestListingImport(unittest.TestCase):
    def test_export_then_import_roundtrip(self):
        doc = generator.make_document(5, seed=7)
        with tempfile.TemporaryDirectory() as td:
            listing = os.path.join(td, "records.lis")
            doc.export_listing(listing)
            self.assertTrue(os.path.getsize(listing) > 100)

            imported = ops.import_listing(listing)
            self.assertEqual(len(imported.events()), len(doc.events()))
            self.assertGreater(len(imported.raw), 100)

            out = os.path.join(td, "imported.tap3")
            imported.save(out)
            reopened = tapfile.open_document(out)
            self.assertEqual(reopened.kind, "tap3")
            self.assertEqual(len(reopened.events()), len(doc.events()))
            self.assertEqual(reopened.to_bytes(), imported.to_bytes())

    def test_import_rejects_empty_listing(self):
        with tempfile.TemporaryDirectory() as td:
            empty = os.path.join(td, "empty.lis")
            with open(empty, "w", encoding="utf-8") as fh:
                fh.write("TAP3 STUDIO LISTING 1.0\n")
            with self.assertRaises(ops.OpsError):
                ops.import_listing(empty)


if __name__ == "__main__":
    unittest.main(verbosity=2)
