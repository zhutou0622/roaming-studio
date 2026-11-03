import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tap3studio import generator, rap, tapfile, validate  # noqa: E402


class TestRapGeneration(unittest.TestCase):
    def setUp(self):
        self.doc = generator.make_document(6, seed=5)
        charge = [n for n in self.doc.nodes.values() if n.name == "charge"][0]
        self.doc.delete_node(charge.node_id)
        self.result = validate.validate(self.doc)
        self.findings = self.result["findings"]

    def test_build_from_findings(self):
        self.assertTrue(self.findings)
        doc = rap.build_rap(self.doc, self.findings)
        self.assertEqual(doc.kind, "rap")
        self.assertEqual(doc.release_label, "RAP1.05")
        self.assertEqual(doc.schema_name, "RAP0105.asn")
        self.assertEqual(doc.schema_mismatch, 0)
        names = [n.name for n in doc.nodes.values()]
        self.assertIn("returnBatch", names)
        self.assertIn("rapBatchControlInfoRap", names)
        self.assertIn("returnDetails", names)
        self.assertTrue(any(n in names for n in ("severeReturn", "fatalReturn")))

    def test_details_match_findings(self):
        doc = rap.build_rap(self.doc, self.findings)
        details = [n for n in doc.nodes.values()
                   if n.name in ("severeReturn", "fatalReturn")]
        events = self.doc.events()
        event_findings = [f for f in self.findings if 0 <= f.get("event", -1) < len(events)]
        file_findings = [f for f in self.findings if not (0 <= f.get("event", -1) < len(events))]
        self.assertEqual(len(details), len({f["event"] for f in event_findings}) + (1 if file_findings else 0))
        self.assertTrue(details)

    def test_roundtrip_and_reopen(self):
        doc = rap.build_rap(self.doc, self.findings)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "return.rap")
            doc.save(path)
            reopened = tapfile.open_document(path)
            self.assertEqual(reopened.kind, "rap")
            self.assertEqual(reopened.schema_name, "RAP0105.asn")
            self.assertEqual(reopened.to_bytes(), doc.to_bytes())

    def test_requires_findings(self):
        clean = generator.make_document(2, seed=2)
        result = validate.validate(clean)
        self.assertEqual(result["findings"], [])
        with self.assertRaises(rap.RapError):
            rap.build_rap(clean, [])

    def test_rap_filename(self):
        self.assertEqual(rap.rap_filename("a/b/T01223_POST.tap3"), "a/b/T01223_POST_RAP.rap")
        self.assertEqual(rap.rap_filename("x/T01223_POST"), "x/T01223_POST_RAP.rap")


if __name__ == "__main__":
    unittest.main(verbosity=2)
