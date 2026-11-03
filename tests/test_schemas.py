import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tap3studio import ber, builder, dictionary, tapfile  # noqa: E402

BIG = os.environ.get("TAP3_PERF_FILE",
                     r"E:\Deepseek工作目录\Romaing Stadio\CDVGBCCUSAK405097_20240320_135240_POST")


def _mod(name):
    return tapfile.all_modules()[name]


class TestSchemaRegistry(unittest.TestCase):
    def test_bundled_modules(self):
        mods = tapfile.all_modules()
        for name in ("TAP0301.asn", "TAP0304.asn", "TAP0309.asn", "TAP0311.asn",
                     "TAP0312.asn", "RAP0101.asn", "RAP0105.asn", "NRT0201.asn"):
            self.assertIn(name, mods, name)
        kinds = {sp["kind"] for sp in tapfile.schema_specs()}
        self.assertEqual(kinds, {"tap3", "rap", "nrtrde"})

    def test_tap_release_matches_schema(self):
        doc = tapfile.open_document("samples/demo.tap3")
        self.assertEqual(doc.kind, "tap3")
        self.assertEqual(doc.release, 11)
        self.assertEqual(doc.schema_name, "TAP0311.asn")
        self.assertEqual(doc.schema_mismatch, 0)

    @unittest.skipUnless(os.path.exists(BIG), "large TAP fixture not available")
    def test_tap312_schema(self):
        doc = tapfile.open_document(BIG)
        self.assertEqual(doc.kind, "tap3")
        self.assertEqual(doc.release, 12)
        self.assertEqual(doc.schema_name, "TAP0312.asn")
        self.assertEqual(doc.schema_mismatch, 0)


class TestRap(unittest.TestCase):
    def _synthetic(self):
        module = _mod("RAP0105.asn")
        spec = {"returnBatch": {
            "rapBatchControlInfoRap": {
                "sender": "26201", "recipient": "22801",
                "rapFileSequenceNumber": "00001",
                "rapFileCreationTimeStamp": {"localTimeStamp": "20240101120000",
                                              "utcTimeOffset": "+0100"},
                "rapFileAvailableTimeStamp": {"localTimeStamp": "20240101120500",
                                               "utcTimeOffset": "+0100"},
                "rapSpecificationVersionNumber": 4,
                "rapReleaseVersionNumber": 5,
            },
            "returnDetails": [],
            "rapAuditControlInfo": {},
        }}
        data = ber.encode_file(builder.build(module, "RapDataInterChange", spec))
        return tapfile.Tap3Document(data, "synthetic.rap")

    def test_kind_and_schema(self):
        doc = self._synthetic()
        self.assertEqual(doc.kind, "rap")
        self.assertEqual(doc.release, 5)
        self.assertEqual(doc.release_label, "RAP1.05")
        self.assertEqual(doc.schema_name, "RAP0105.asn")
        self.assertEqual(doc.schema_mismatch, 0)

    def test_annotated_fields_and_roundtrip(self):
        doc = self._synthetic()
        names = [n.name for n in doc.nodes.values()]
        for expected in ("returnBatch", "rapBatchControlInfoRap", "sender",
                         "rapReleaseVersionNumber"):
            self.assertIn(expected, names)
        self.assertEqual(doc.to_bytes(), doc.raw)

    def test_dictionary_for_rap_type(self):
        entry = dictionary.dictionary("RapBatchControlInfo", "rapBatchControlInfo")
        self.assertEqual(entry["type"], "RapBatchControlInfo")
        self.assertIn("ReturnBatch", entry["asn1"][0])
        self.assertIn("ReturnBatch", entry["parents"])


class TestNonTapBatch(unittest.TestCase):
    def test_rap_is_skipped_by_batch(self):
        from tap3studio import batch
        module = _mod("RAP0105.asn")
        spec = {"returnBatch": {
            "rapBatchControlInfoRap": {
                "sender": "26201", "recipient": "22801",
                "rapFileSequenceNumber": "00001",
                "rapFileCreationTimeStamp": {"localTimeStamp": "20240101120000",
                                              "utcTimeOffset": "+0100"},
                "rapFileAvailableTimeStamp": {"localTimeStamp": "20240101120500",
                                               "utcTimeOffset": "+0100"},
                "rapSpecificationVersionNumber": 4,
                "rapReleaseVersionNumber": 5},
            "returnDetails": [], "rapAuditControlInfo": {}}}
        data = ber.encode_file(builder.build(module, "RapDataInterChange", spec))
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "return.rap")
            with open(path, "wb") as fh:
                fh.write(data)
            rows = batch.scan([td])
            self.assertEqual(rows[0]["status"], "SKIPPED")
            self.assertEqual(batch.summary(rows)["skipped"], 1)


class TestNrtrde(unittest.TestCase):
    def test_kind_and_schema(self):
        module = _mod("NRT0201.asn")
        spec = {"specificationVersionNumber": 3, "releaseVersionNumber": 2,
                "sender": "26201", "recipient": "22801"}
        data = ber.encode_file(builder.build(module, "Nrtrde", spec))
        doc = tapfile.Tap3Document(data, "synthetic.nrtrde")
        self.assertEqual(doc.kind, "nrtrde")
        self.assertEqual(doc.schema_name, "NRT0201.asn")
        self.assertEqual(doc.schema_mismatch, 0)
        names = [n.name for n in doc.nodes.values()]
        self.assertIn("specificationVersionNumber", names)
        self.assertIn("sender", names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
