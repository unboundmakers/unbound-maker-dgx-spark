import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / "scripts/asset_builder.py"


class ContractTests(unittest.TestCase):
    def call(self, *args, isolated=False):
        # -I also ignores inherited PYTHONPATH (used by Spark's USD runtime).
        command = [sys.executable] + (["-I", "-S"] if isolated else [])
        result = subprocess.run(command + [str(SCRIPT), *args],
                                capture_output=True, text=True)
        self.assertTrue(result.stdout.strip(), "CLI must return JSON: " + result.stderr)
        return result

    def test_capabilities_work_without_usd(self):
        result = self.call("capabilities", isolated=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["templates"], ["flyingcat-v1"])
        self.assertFalse(data["physics_ready"])
        self.assertEqual(data["scale_range"], [0.5, 2.0])

    def test_invalid_requests_never_create_output(self):
        invalid = [[], {}, {"template_id": "other", "schema_version": 1},
                   {"schema_version": True, "template_id": "flyingcat-v1"}]
        base = {"schema_version": 1, "template_id": "flyingcat-v1"}
        invalid += [dict(base, scale=value) for value in
                    (True, "1", 0, 0.49, 2.01, 10 ** 400, float("nan"), float("inf"))]
        invalid += [dict(base, body_color=value) for value in
                    (None, "blue", "#123", "#ffffff; touch nope", 123)]
        invalid += [dict(base, **extra) for extra in
                    ({"mass_kg": 2}, {"source_path": "/tmp/other.usd"},
                     {"command": "echo hello"})]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request, output = root / "request.json", root / "result"
            for data in invalid:
                with self.subTest(data=data):
                    request.write_text(json.dumps(data))
                    result = self.call("build", "--request", str(request),
                                       "--output", str(output))
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(json.loads(result.stdout)["error"]["code"],
                                     "invalid_request")
                    self.assertFalse(output.exists())

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            request = Path(directory) / "request.json"
            request.write_text('{"schema_version":1,"template_id":"flyingcat-v1",'
                               '"scale":1,"scale":2}')
            result = self.call("build", "--request", str(request), "--output",
                               str(Path(directory) / "result"))
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(json.loads(result.stdout)["error"]["code"], "invalid_request")

    def test_bad_json_and_missing_input_report_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for content in (None, "not json"):
                if content:
                    (root / "request.json").write_text(content)
                result = self.call("build", "--request", str(root / "request.json"),
                                   "--output", str(root / "result"))
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(json.loads(result.stdout)["status"], "failed")
                self.assertFalse((root / "result").exists())

    def test_missing_usd_is_not_a_mock_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "request.json").write_text(json.dumps({
                "schema_version": 1, "template_id": "flyingcat-v1"}))
            result = self.call("build", "--request", str(root / "request.json"),
                               "--output", str(root / "result"), isolated=True)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(json.loads(result.stdout)["error"]["code"], "missing_dependency")
            self.assertFalse((root / "result").exists())


if __name__ == "__main__":
    unittest.main()
