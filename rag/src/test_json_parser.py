import json
import tempfile
import unittest
from pathlib import Path

from docling_parser import AuditDocumentParser


class JsonParserTest(unittest.TestCase):
    def test_preserves_paths_and_ignores_images(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.json"
            path.write_text(json.dumps({"Findings": [{"Severity": "High", "image_context": "skip"}]}), encoding="utf-8")
            parsed = AuditDocumentParser().parse(str(path), report_id="R1")
            self.assertIn("Findings > [1] > Severity: High", parsed.full_text)
            self.assertNotIn("skip", parsed.full_text)


if __name__ == "__main__":
    unittest.main()
