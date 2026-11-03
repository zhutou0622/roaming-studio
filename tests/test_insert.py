import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tap3studio import generator, tapfile, validate  # noqa: E402


class TestInsert(unittest.TestCase):
    def setUp(self):
        self.doc = generator.make_document(2, seed=4)
        self.charge_detail = [n for n in self.doc.nodes.values()
                              if n.type_name == "ChargeDetail" and n.constructed][0]

    def test_options_expose_schema_fields(self):
        opts = self.doc.insert_options(self.charge_detail.node_id)
        names = [o["field"] for o in opts["child"]["options"]]
        self.assertIn("chargeDetailTimeStamp", names)
        self.assertIn("charge", names)
        present = {o["field"]: o["present"] for o in opts["child"]["options"]}
        self.assertTrue(present["charge"])
        self.assertFalse(present["chargeDetailTimeStamp"])
        # sibling of a ChargeDetail item offers the sequence-of item type
        self.assertEqual(opts["sibling"]["kind"], "sequence_of")
        self.assertEqual(opts["sibling"]["options"][0]["type"], "ChargeDetail")

    def test_insert_child_leaf_and_sequence(self):
        res = self.doc.insert_node(self.charge_detail.node_id, "child",
                                   "chargeDetailTimeStamp", "", "20240101120000")
        node = self.doc.node(res["id"])
        self.assertEqual(node.field_name, "chargeDetailTimeStamp")
        self.assertTrue(node.constructed)
        self.assertTrue(self.doc.modified_paths)

        # a sequence-valued child is created empty and can receive children
        opts = self.doc.insert_options(self.charge_detail.node_id)
        ts = [o for o in opts["child"]["options"] if o["field"] == "chargeDetailTimeStamp"][0]
        self.assertTrue(ts["present"])

    def test_insert_sibling_in_list(self):
        lst = [x for x in self.doc.nodes.values() if x.type_name == "ChargeDetailList"][0]
        before = len(lst.children)
        res = self.doc.insert_node(lst.children[0].node_id, "sibling", "item", "", "")
        self.assertEqual(len(self.doc.node(lst.node_id).children), before + 1)
        self.assertIn("ChargeDetail[", res["path"])

    def test_invalid_field_rejected(self):
        with self.assertRaises(tapfile.Tap3Error):
            self.doc.insert_node(self.charge_detail.node_id, "child", "notAField", "", "")
        with self.assertRaises(tapfile.Tap3Error):
            self.doc.insert_node(self.charge_detail.node_id, "child", "charge", "x", "")

    def test_inserted_document_roundtrip(self):
        self.doc.insert_node(self.charge_detail.node_id, "child",
                             "chargeDetailTimeStamp", "", "20240101120000")
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "inserted.tap3")
            self.doc.save(path)
            reopened = tapfile.open_document(path)
            names = [n.name for n in reopened.nodes.values()]
            self.assertIn("chargeDetailTimeStamp", names)
            result = validate.validate(reopened)
            self.assertEqual(result["errors"], 0, result["findings"][:3])


if __name__ == "__main__":
    unittest.main(verbosity=2)
