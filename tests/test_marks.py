import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tap3studio import generator, tapfile  # noqa: E402

BIG = os.environ.get("TAP3_PERF_FILE",
                     r"E:\Deepseek工作目录\Romaing Stadio\CDVGBCCUSAK405097_20240320_135240_POST")


class TestModificationMarks(unittest.TestCase):
    def setUp(self):
        self.doc = generator.make_document(6, seed=11)

    def test_set_value_marks_path_and_keeps_ancestry(self):
        leaf = [n for n in self.doc.nodes.values() if n.name == "imsi"][0]
        path = leaf.path()
        self.assertFalse(self.doc.is_modified(leaf))
        self.doc.set_value(leaf.node_id, "262019999999999")
        node = self.doc.find_by_path(path)
        self.assertIsNotNone(node, "path must still resolve after the edit")
        self.assertTrue(self.doc.is_modified(node))
        detail = self.doc.node_detail(node.node_id)
        self.assertTrue(detail["modified"])
        self.assertGreaterEqual(len(detail["ancestors"]), 3)

    def test_replace_marks_every_changed_value(self):
        changed = self.doc.replace("26201", "26299")
        self.assertGreater(len(changed), 0)
        marked = [p for p in self.doc.modified_paths]
        self.assertEqual(len(marked), len({c["path"] for c in changed}))
        for c in changed:
            self.assertTrue(c["path"] in self.doc.modified_paths)

    def test_marks_survive_save(self):
        leaf = [n for n in self.doc.nodes.values() if n.name == "msisdn"][0]
        path = leaf.path()
        self.doc.set_value(leaf.node_id, "491710009999999")
        import tempfile
        out = os.path.join(tempfile.gettempdir(), "tap3studio_marks.tap3")
        self.doc.save(out)
        try:
            self.assertIn(path, self.doc.modified_paths)
            reloaded = tapfile.open_document(out)
            self.assertNotIn(path, reloaded.modified_paths)  # fresh session = no marks
        finally:
            if os.path.exists(out):
                os.remove(out)

    def test_clear_marks(self):
        leaf = [n for n in self.doc.nodes.values() if n.name == "charge"][0]
        self.doc.set_value(leaf.node_id, "12345")
        self.assertTrue(self.doc.modified_paths)
        self.doc.modified_paths.clear()
        self.assertFalse(self.doc.is_modified(leaf))


@unittest.skipUnless(os.path.exists(BIG), "large TAP fixture not available")
class TestLargeFileMarks(unittest.TestCase):
    def test_edit_keeps_document_and_marks_leaf(self):
        doc = tapfile.open_document(BIG)
        leaf = [n for n in doc.nodes.values() if n.name == "imsi"][0]
        path = leaf.path()
        doc.set_value(leaf.node_id, "262019999999999")
        node = doc.find_by_path(path)
        self.assertTrue(doc.is_modified(node))
        self.assertEqual(doc.find_by_path(path).value_text, "262019999999999")
        # the rest of the document is untouched
        self.assertEqual(doc.header()["sender"], "VGBCC")
        self.assertEqual(len(doc.events()), 3883)


if __name__ == "__main__":
    unittest.main(verbosity=2)
