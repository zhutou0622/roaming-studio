import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tap3studio import generator, tapfile, validate  # noqa: E402

BIG = os.environ.get("TAP3_PERF_FILE",
                     r"E:\Deepseek工作目录\Romaing Stadio\CDVGBCCUSAK405097_20240320_135240_POST")


def _first(doc, name):
    for node in doc.nodes.values():
        if node.name == name:
            return node
    return None


class TestValidationFixes(unittest.TestCase):
    def test_file_type_indicator_is_optional(self):
        doc = generator.make_document(3, seed=3)
        node = _first(doc, "fileTypeIndicator")
        self.assertIsNotNone(node)
        doc.delete_node(node.node_id)
        result = validate.validate(doc)
        self.assertFalse(any(f["code"] == "TAP-002" and "fileTypeIndicator" in f["message"]
                             for f in result["findings"]))
        self.assertEqual(result["errors"], 0, result["findings"])

    def test_duplicate_charge_detail_uses_deduplicated_total(self):
        doc = generator.make_document(4, seed=3)
        detail = next(n for n in doc.nodes.values()
                      if n.type_name == "ChargeDetail" and n.constructed)
        charge = int(next(c for c in detail.children if c.name == "charge").value_text or 0)
        doc.clone_node(detail.node_id)

        # tag the clone as chargeType 03, keep amount/units identical
        clones = [n for n in doc.nodes.values()
                  if n.type_name == "ChargeDetail" and n.constructed
                  and n.parent_id == detail.parent_id]
        self.assertEqual(len(clones), 2)
        clone = clones[-1]
        for child in clone.children:
            if child.name == "chargeType":
                doc.set_value(child.node_id, "03")

        # the audit total stays at the original (de-duplicated) amount
        result = validate.validate(doc)
        self.assertFalse(any(f["code"] == "AUD-004" for f in result["findings"]))
        self.assertTrue(any(f["code"] == "AUD-006" for f in result["findings"]),
                        result["findings"])
        self.assertEqual(result["errors"], 0, result["findings"])

    def test_tax_mismatch_is_reported(self):
        doc = generator.make_document(3, seed=3)
        tax = _first(doc, "totalTaxValue")
        self.assertIsNotNone(tax)
        doc.set_value(tax.node_id, str(int(tax.value_text or 0) + 7))
        result = validate.validate(doc)
        self.assertTrue(any(f["code"] == "AUD-007" for f in result["findings"]),
                        result["findings"])

    @unittest.skipUnless(os.path.exists(BIG), "large TAP fixture not available")
    def test_large_file_has_no_errors_after_fix(self):
        doc = tapfile.open_document(BIG)
        result = validate.validate(doc)
        self.assertEqual(result["errors"], 0, [f for f in result["findings"]
                                                if f["severity"] == "error"])
        self.assertTrue(any(f["code"] == "AUD-006" for f in result["findings"]))
        self.assertFalse(any(f["code"] == "TAP-002" for f in result["findings"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
