import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tap3studio import dictionary, generator, tapfile, validate  # noqa: E402


class TestDictionary(unittest.TestCase):
    def test_teleservice_entry(self):
        d = dictionary.dictionary("TeleServiceCode", "teleServiceCode")
        self.assertEqual(d["type"], "TeleServiceCode")
        self.assertEqual(d["field"], "teleServiceCode")
        self.assertEqual(len(d["values"]), 16)
        self.assertEqual(d["values"][1]["code"], "10")
        self.assertEqual(len(d["validations"]), 4)
        self.assertIn("BasicServiceCode", d["parents"])
        self.assertTrue(any("BasicServiceCode ::= [APPLICATION 426] CHOICE" in line
                            for line in d["asn1"]))
        self.assertEqual(d["footer"], "Text extracted from GSM TD57 standard")

    def test_leaf_types_have_conditionality(self):
        d = dictionary.dictionary("Imsi", "imsi")
        self.assertTrue(d["conditionality"])
        self.assertIn("BCD", " ".join(d["description"]))

    def test_unknown_type(self):
        with self.assertRaises(KeyError):
            dictionary.dictionary("NotATapType")

    def test_every_annotated_node_type_has_entry(self):
        doc = generator.make_document(3, seed=2)
        seen = set()
        for n in doc.nodes.values():
            if n.type_name and n.type_name not in seen:
                seen.add(n.type_name)
                d = dictionary.dictionary(n.type_name, n.name)
                self.assertTrue(d["description"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
