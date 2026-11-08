import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from lab.graphs import activation_extraction


FIXTURE = {
    "tokens": ["A", "B"], "activation_norms": [[1.0, 2.0], [3.0, 4.0]],
    "clean_score": 2.0, "corrupt_score": -1.0, "denominator": 3.0,
    "patches": [{"layer": 0, "position": 1, "patched_score": -1.5,
                 "effect": -0.5, "recovery": -1 / 6}],
}


class GraphTests(unittest.TestCase):
    def test_observations_are_separate_from_intervention_effects(self):
        extraction = activation_extraction(FIXTURE)
        self.assertEqual(len(extraction["nodes"]), 6)
        self.assertEqual(len(extraction["edges"]), 5)
        architecture = [e for e in extraction["edges"] if e["evidence_kind"] == "architecture"]
        self.assertTrue(all(e["source"].startswith("state_L0") and e["target"].startswith("state_L1")
                            for e in architecture))
        causal = [e for e in extraction["edges"] if e["evidence_kind"] == "node_intervention"]
        self.assertEqual(len(causal), 1)
        self.assertEqual(causal[0]["effect_logit_diff"], -0.5)
        self.assertEqual(causal[0]["target"], "metric")
        self.assertEqual(causal[0]["weight"], 1.0)

    def test_bad_positions_and_nonfinite_values_are_rejected(self):
        for location, value in (("position", 2), ("effect", float("nan"))):
            bad = copy.deepcopy(FIXTURE)
            bad["patches"][0][location] = value
            with self.assertRaises(ValueError):
                activation_extraction(bad)

    @unittest.skipUnless(os.environ.get("GRAPHIFY_PYTHON"), "set GRAPHIFY_PYTHON for real exporter test")
    def test_real_graphify_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = root / "patching.json"
            result.write_text(json.dumps(FIXTURE), encoding="utf-8")
            output = root / "graph"
            subprocess.run([
                sys.executable, "-m", "lab.graphs", "--results", str(result),
                "--output", str(output), "--graphify-python", os.environ["GRAPHIFY_PYTHON"],
            ], check=True, capture_output=True, text=True)
            graph = json.loads((output / "graph.json").read_text(encoding="utf-8"))
            self.assertTrue(graph["directed"])
            causal = [e for e in graph["links"] if e["evidence_kind"] == "node_intervention"]
            self.assertEqual(causal[0]["effect_logit_diff"], -0.5)
            for name in ("graph.html", "GRAPH_REPORT.md", "extraction.json", "diagnostics.json"):
                self.assertTrue((output / name).is_file(), name)
            report = (output / "GRAPH_REPORT.md").read_text(encoding="utf-8")
            self.assertIn("0 input", report)
            self.assertIn("CDN", report)


if __name__ == "__main__":
    unittest.main()
