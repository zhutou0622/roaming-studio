import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tap3studio import batch, generator, rules, tapfile, validate  # noqa: E402


class TestProfiles(unittest.TestCase):
    def setUp(self):
        self.doc = generator.make_document(6, seed=5)
        self.clean = validate.validate(self.doc)
        self.assertEqual(self.clean["errors"], 0)

    def test_catalog_complete(self):
        cat = rules.catalog()
        codes = {r["code"] for r in cat["rules"]}
        self.assertIn("AUD-004", codes)
        self.assertIn("EVT-009", codes)
        self.assertEqual(cat["thresholds"]["maxDurationSeconds"], 172800)

    def test_suppress_rule(self):
        charge = [n for n in self.doc.nodes.values() if n.name == "charge"][0]
        self.doc.delete_node(charge.node_id)
        broken = validate.validate(self.doc)
        self.assertTrue(any(f["code"] == "AUD-004" for f in broken["findings"]))
        prof = rules.normalize({"name": "test", "rules": {"AUD-004": "off"}})
        result = validate.validate(self.doc, prof)
        self.assertFalse(any(f["code"] == "AUD-004" for f in result["findings"]))
        self.assertGreater(result["suppressed"], 0)
        self.assertEqual(result["profile"], "test")

    def test_severity_override(self):
        # remove the charge to trigger EVT-008 (warning by default)
        for node in [n for n in self.doc.nodes.values() if n.name == "charge"][:1]:
            self.doc.delete_node(node.node_id)
        default = validate.validate(self.doc)
        evt8 = [f for f in default["findings"] if f["code"] == "EVT-008"]
        self.assertTrue(evt8 and evt8[0]["severity"] == "warning")
        prof = rules.normalize({"rules": {"EVT-008": "error"}})
        overridden = validate.validate(self.doc, prof)
        evt8 = [f for f in overridden["findings"] if f["code"] == "EVT-008"]
        self.assertTrue(evt8 and evt8[0]["severity"] == "error")

    def test_thresholds(self):
        prof = rules.normalize({"thresholds": {"maxDurationSeconds": 1}})
        result = validate.validate(self.doc, prof)
        self.assertTrue(any(f["code"] == "EVT-006" for f in result["findings"]))

    def test_charge_tolerance(self):
        audit = [n for n in self.doc.nodes.values() if n.name == "totalCharge"][0]
        current = int(audit.value_text or "0")
        self.doc.set_value(audit.node_id, str(current + 1))
        strict = validate.validate(self.doc)
        self.assertTrue(any(f["code"] == "AUD-004" for f in strict["findings"]))
        loose = validate.validate(self.doc, rules.normalize({"thresholds": {"chargeTolerance": 5}}))
        self.assertFalse(any(f["code"] == "AUD-004" for f in loose["findings"]))

    def test_invalid_profile(self):
        with self.assertRaises(rules.ProfileError):
            rules.normalize({"rules": "nope"})
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "bad.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{not json")
            with self.assertRaises(rules.ProfileError):
                rules.normalize(path=path)


class TestBatch(unittest.TestCase):
    def test_scan_csv_xlsx(self):
        with tempfile.TemporaryDirectory() as td:
            good = os.path.join(td, "good.tap3")
            generator.make_document(3, seed=2).save(good)
            bad = os.path.join(td, "broken.bin")
            with open(bad, "wb") as fh:
                fh.write(b"\x61\x82\x10\x00")
            rows = batch.scan([td])
            self.assertEqual(len(rows), 2)
            by_name = {r["file"]: r for r in rows}
            self.assertEqual(by_name["good.tap3"]["status"], "OK")
            self.assertEqual(by_name["good.tap3"]["records"], 3)
            self.assertEqual(by_name["broken.bin"]["status"], "FAILED")

            csv_path = os.path.join(td, "scan.csv")
            xlsx_path = os.path.join(td, "scan.xlsx")
            batch.write_csv(rows, csv_path)
            batch.write_xlsx(rows, xlsx_path)
            self.assertTrue(os.path.getsize(csv_path) > 50)
            self.assertTrue(os.path.getsize(xlsx_path) > 1000)

            summary = batch.summary(rows)
            self.assertEqual(summary["files"], 2)
            self.assertEqual(summary["ok"], 1)
            self.assertEqual(summary["failed"], 1)

    def test_batch_profile_suppression(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "doc.tap3")
            doc = generator.make_document(4, seed=2)
            charge = [n for n in doc.nodes.values() if n.name == "charge"][0]
            doc.delete_node(charge.node_id)
            doc.save(path)
            strict = batch.scan([td])
            self.assertEqual(strict[0]["status"], "ERRORS")
            loose = batch.scan([td], rules.normalize({"rules": {"AUD-004": "off"}}))
            self.assertEqual(loose[0]["status"], "OK")


if __name__ == "__main__":
    unittest.main(verbosity=2)
