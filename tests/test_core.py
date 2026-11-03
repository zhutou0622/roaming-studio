import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tap3studio import ber, generator, ops, tapfile, validate  # noqa: E402


class TestSchema(unittest.TestCase):
    def test_modules_loaded(self):
        mods = tapfile.all_modules()
        self.assertIn("TAP0311.asn", mods)
        m = mods["TAP0311.asn"]
        self.assertIn("TransferBatch", m.types)
        self.assertIn("MobileOriginatedCall", m.types)
        self.assertEqual(m.types["TransferBatch"].effective_tag(m), ("APPLICATION", 1))

    def test_bcd(self):
        self.assertEqual(tapfile.digits_to_bcd("26201"), bytes.fromhex("2620 1f".replace(" ", "")))
        self.assertEqual(tapfile.bcd_to_digits(bytes.fromhex("26201f")), "26201")


class TestDocument(unittest.TestCase):
    def setUp(self):
        self.doc = generator.make_document(9, seed=3)

    def test_release_and_events(self):
        self.assertEqual(self.doc.release, 11)
        self.assertEqual(len(self.doc.events()), 9)
        self.assertEqual(self.doc.schema_mismatch, 0)

    def test_roundtrip_bytes(self):
        self.assertEqual(self.doc.to_bytes(), self.doc.raw)

    def test_statistics(self):
        st = self.doc.statistics()
        self.assertEqual(st["auditCount"], 9)
        self.assertTrue(st["countMatches"])
        self.assertGreater(st["chargeSum"], 0)

    def test_edit_roundtrip(self):
        node = [n for n in self.doc.nodes.values() if n.name == "imsi"][0]
        self.doc.set_value(node.node_id, "262019999999999")
        reloaded = tapfile.Tap3Document(self.doc.to_bytes(), "edited.tap3")
        imsi = [n.value_text for n in reloaded.nodes.values() if n.name == "imsi"][0]
        self.assertEqual(imsi, "262019999999999")
        self.assertEqual(reloaded.release, 11)

    def test_replace(self):
        changed = self.doc.replace("22801", "22802")
        self.assertGreaterEqual(len(changed), 1)
        self.assertEqual(self.doc.header()["recipient"], "22802")


class TestValidation(unittest.TestCase):
    def test_clean_file(self):
        doc = generator.make_document(6, seed=5)
        r = validate.validate(doc)
        self.assertEqual(r["errors"], 0, r["findings"])
        self.assertEqual(r["warnings"], 0, r["findings"])

    def test_count_mismatch(self):
        doc = generator.make_document(6, seed=5)
        n = [x for x in doc.nodes.values() if x.name == "callEventDetailsCount"][0]
        doc.set_value(n.node_id, "99")
        r = validate.validate(doc)
        self.assertTrue(any(f["code"] == "AUD-003" for f in r["findings"]))

    def test_charge_mismatch(self):
        doc = generator.make_document(6, seed=5)
        charge = [x for x in doc.nodes.values() if x.name == "charge"][0]
        doc.delete_node(charge.node_id)
        r = validate.validate(doc)
        self.assertTrue(any(f["code"] == "AUD-004" for f in r["findings"]))


class TestOps(unittest.TestCase):
    def test_merge_split_export(self):
        d1 = generator.make_document(4, seed=1)
        d2 = generator.make_document(4, seed=2)
        merged = ops.merge_documents([d1, d2])
        self.assertEqual(len(merged.events()), 8)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "m.tap3")
            merged.save(path)
            reloaded = tapfile.open_document(path)
            self.assertEqual(len(reloaded.events()), 8)
            parts = ops.split_document(reloaded, os.path.join(td, "p_"), chunk=3)
            self.assertEqual(len(parts), 3)
            for p in parts:
                self.assertTrue(os.path.getsize(p) > 0)
            csv_path = os.path.join(td, "out.csv")
            reloaded.export_csv(csv_path)
            self.assertTrue(os.path.getsize(csv_path) > 0)


class TestBer(unittest.TestCase):
    def test_length_forms(self):
        node = ber.BerNode("APPLICATION", 3, True)
        for i in range(3):
            node.children.append(ber.BerNode("APPLICATION", 199, True))
        data = ber.encode_file(node)
        decoded, end = ber.decode_element(data, 0)
        self.assertEqual(end, len(data))
        self.assertEqual(len(decoded.children), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
