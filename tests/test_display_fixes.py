import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tap3studio import generator, tapfile  # noqa: E402

BIG = os.environ.get("TAP3_PERF_FILE",
                     r"E:\Deepseek工作目录\Romaing Stadio\CDVGBCCUSAK405097_20240320_135240_POST")


@unittest.skipUnless(os.path.exists(BIG), "large TAP fixture not available")
class TestDisplayFixes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = tapfile.open_document(BIG)

    def test_calling_number_is_decoded_as_bcd(self):
        calls = [n for n in self.doc.nodes.values() if n.name == "callingNumber"]
        self.assertTrue(calls)
        for node in calls[:20]:
            self.assertEqual(node.semantic, "bcd", node.type_name)
            self.assertRegex(node.value_text, r"^\d+$")
            self.assertNotIn("\ufffd", node.value_text)

    def test_rec_entity_map(self):
        entities = self.doc.rec_entities()
        self.assertIn("2", entities)
        self.assertEqual(entities["2"]["typeLabel"], "MSC")
        self.assertEqual(entities["2"]["id"], "12844440025")
        self.assertIn("0", entities)

    def test_editing_calling_number_keeps_bcd(self):
        node = [n for n in self.doc.nodes.values() if n.name == "callingNumber"][0]
        self.doc.set_value(node.node_id, "4917012345678")
        edited = [n for n in self.doc.nodes.values() if n.name == "callingNumber"][0]
        self.assertEqual(edited.value_text, "4917012345678")
        self.assertEqual(edited.semantic, "bcd")
        self.assertEqual(edited.payload, bytes.fromhex("4917012345678f"))


class TestGeneratedSemantics(unittest.TestCase):
    def test_address_string_digits_encodes_bcd(self):
        doc = generator.make_document(2, seed=2)
        node = [n for n in doc.nodes.values() if n.name == "calledNumber"][0]
        self.assertEqual(node.semantic, "bcd")
        self.assertRegex(node.value_text, r"^\d+$")


if __name__ == "__main__":
    unittest.main(verbosity=2)
