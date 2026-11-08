import http.client
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import subprocess
import sys
import unittest
from unittest.mock import patch

from lab.ui import LabApplication, main, make_server
from lab.runtime import MODEL


PAYLOAD = {"clean": "John gave the bag to", "corrupt": "Mary gave the bag to",
           "target": "Mary", "contrast": "John", "positions": "changed,last", "threads": 4}
MEMORY = {"available_gib": 4, "total_gib": 16, "minimum_gib": 3, "can_run": True}


class UiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        (self.root / "ui").mkdir()
        (self.root / "ui/index.html").write_text("<h1>Local</h1>", encoding="utf-8")
        (self.root / "secret.txt").write_text("outside", encoding="utf-8")
        self.commands = []
        self.entered, self.release = threading.Event(), threading.Event()
        self.block = False
        self.fail_command = False
        self.fail_graph = False
        self.memory = dict(MEMORY)
        self.app = LabApplication(self.root, "graphify-python", runner=self.runner,
                                  memory_reader=lambda: self.memory)
        self.server = make_server(self.app, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.release.set()
        self.wait_job()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def runner(self, command, log):
        self.commands.append(command)
        log("executing fixture")
        self.entered.set()
        if self.block:
            self.release.wait(2)
        if self.fail_command:
            raise RuntimeError("fixture failed")
        output = Path(command[command.index("--output") + 1])
        if "lab.patching" in command:
            output.write_text(json.dumps({"tokens": ["fixture"], "clean_score": 2}), encoding="utf-8")
        else:
            result_path = command[command.index("--results") + 1] if "--results" in command else None
            if self.fail_graph:
                self.assertEqual(json.loads(Path(result_path).read_text(encoding="utf-8"))["tokens"], ["fixture"])
                raise RuntimeError("fixture graph export failed")
            output.mkdir(parents=True, exist_ok=True)
            (output / "graph.html").write_text("<h1>Graph</h1>", encoding="utf-8")
            (output / "graph.json").write_text(json.dumps({
                "nodes": [], "links": [], "source_file": result_path}), encoding="utf-8")

    def request(self, method, path, value=None, *, raw=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        body = raw if raw is not None else json.dumps(value).encode("utf-8") if value is not None else None
        request_headers = {"Content-Type": "application/json"} if method == "POST" else {}
        request_headers.update(headers or {})
        conn.request(method, path, body, headers=request_headers)
        response = conn.getresponse()
        data, response_headers = response.read(), dict(response.getheaders())
        code = response.status
        conn.close()
        if response_headers.get("Content-Type", "").startswith("application/json"):
            data = json.loads(data)
        return code, data, response_headers

    def wait_job(self):
        deadline = time.monotonic() + 3
        while self.app.job["status"] == "running" and time.monotonic() < deadline:
            self.release.wait(0.01) if not self.release.is_set() else time.sleep(0.01)
        self.assertNotEqual(self.app.job["status"], "running")

    def test_static_state_and_result_export(self):
        code, content, headers = self.request("GET", "/")
        self.assertEqual(code, 200)
        self.assertIn("charset=utf-8", headers["Content-Type"])
        self.assertIn(b"Local", content)
        code, state, _ = self.request("GET", "/api/state")
        self.assertEqual(code, 200)
        self.assertEqual(state["job"]["status"], "idle")
        self.assertIsNone(state["result"])
        self.assertEqual(state["memory"]["minimum_gib"], 3)
        self.assertEqual(state["graphify"], {"available": True, "message": None})
        self.assertEqual(self.request("POST", "/api/run", PAYLOAD)[0], 202)
        self.wait_job()
        self.assertEqual(self.app.job["status"], "success")
        self.assertEqual(len(self.commands), 2)
        self.assertIn("--clean=" + PAYLOAD["clean"], self.commands[0])
        self.assertEqual(self.request("GET", "/graphs/circuit")[0], 200)
        graph = json.loads((self.root / "artifacts/circuit/graph.json").read_text(encoding="utf-8"))
        self.assertEqual(graph["source_file"], str(self.root / "artifacts/patching.json"))
        code, result, headers = self.request("GET", "/api/export")
        self.assertEqual(code, 200)
        self.assertEqual(result["tokens"], ["fixture"])
        self.assertIn("attachment", headers["Content-Disposition"])

    def test_missing_graphify_keeps_experiments_available(self):
        missing = LabApplication(self.root, self.root / "missing-python.exe", memory_reader=lambda: self.memory)
        self.assertFalse(missing.graphify_available)
        self.app.graphify_available = missing.graphify_available
        _, state, _ = self.request("GET", "/api/state")
        self.assertFalse(state["graphify"]["available"])
        code, error, _ = self.request("POST", "/api/repository", {})
        self.assertEqual(code, 503)
        self.assertIn("--graphify-python", error["error"])
        self.assertEqual(self.request("POST", "/api/run", PAYLOAD)[0], 202)
        self.wait_job()
        _, state, _ = self.request("GET", "/api/state")
        self.assertEqual(state["job"]["status"], "success")
        self.assertIn("Graphify is unavailable", state["job"]["warning"])
        self.assertEqual(state["result"]["tokens"], ["fixture"])
        self.assertFalse(state["circuit"]["available"])
        self.assertEqual(len(self.commands), 1)

    def test_graph_export_failure_preserves_new_measurements(self):
        self.fail_graph = True
        result_path = self.root / "artifacts/patching.json"
        graph = self.root / "artifacts/circuit/graph.html"
        graph.parent.mkdir(parents=True)
        result_path.write_text('{"previous": true}', encoding="utf-8")
        graph.write_text("old graph", encoding="utf-8")
        old_timestamp = graph.stat().st_mtime_ns - 1_000_000_000
        os.utime(graph, ns=(old_timestamp, old_timestamp))
        self.assertEqual(self.request("POST", "/api/run", PAYLOAD)[0], 202)
        self.wait_job()
        _, state, _ = self.request("GET", "/api/state")
        self.assertEqual(state["job"]["status"], "success")
        self.assertIn("fixture graph export failed", state["job"]["warning"])
        self.assertEqual(state["result"]["tokens"], ["fixture"])
        self.assertEqual(json.loads(result_path.read_text(encoding="utf-8")), state["result"])
        self.assertFalse(state["circuit"]["available"])
        self.assertEqual(self.request("GET", "/graphs/circuit")[0], 404)

    def test_low_memory_rejects_model_but_allows_repository(self):
        self.memory.update(available_gib=2, can_run=False)
        self.assertEqual(self.request("POST", "/api/run", PAYLOAD)[0], 503)
        self.assertEqual(self.commands, [])
        self.assertEqual(self.request("POST", "/api/repository", {})[0], 202)
        self.wait_job()
        self.assertIn("--repo", self.commands[0])

    def test_external_result_refresh_and_stale_graph(self):
        artifacts = self.root / "artifacts"
        artifacts.mkdir()
        result_path = artifacts / "patching.json"
        result_path.write_text('{"from_terminal": true}', encoding="utf-8")
        self.assertEqual(self.request("GET", "/api/export")[1], {"from_terminal": True})
        graph = artifacts / "circuit/graph.html"
        graph.parent.mkdir()
        graph.write_text("graph", encoding="utf-8")
        timestamp = result_path.stat().st_mtime_ns
        os.utime(graph, ns=(timestamp - 1_000_000, timestamp - 1_000_000))
        self.assertFalse(self.request("GET", "/api/state")[1]["circuit"]["available"])
        os.utime(graph, ns=(timestamp + 1_000_000, timestamp + 1_000_000))
        self.assertTrue(self.request("GET", "/api/state")[1]["circuit"]["available"])

    def test_import_does_not_load_model_runtime(self):
        subprocess.run([sys.executable, "-c", "import lab.ui, sys; assert 'torch' not in sys.modules"],
                       check=True, capture_output=True)

    def test_open_reuses_existing_local_panel(self):
        response = io.BytesIO(json.dumps({"model": {"name": MODEL}}).encode())
        with patch.object(sys, "argv", ["lab.ui", "--open"]), \
                patch("urllib.request.urlopen", return_value=response), \
                patch("webbrowser.open") as browser, patch("lab.ui.make_server") as bind:
            main()
        browser.assert_called_once_with("http://127.0.0.1:8765")
        bind.assert_not_called()

    def test_busy_jobs_and_failure_preserve_previous_result(self):
        self.app.result = {"previous": True}
        artifacts = self.root / "artifacts"
        artifacts.mkdir()
        previous = artifacts / "patching.json"
        previous.write_text('{"previous": true}', encoding="utf-8")
        self.block, self.fail_command = True, True
        self.assertEqual(self.request("POST", "/api/run", PAYLOAD)[0], 202)
        self.assertTrue(self.entered.wait(1))
        self.assertEqual(self.request("POST", "/api/repository", {})[0], 409)
        self.assertEqual(self.request("GET", "/api/state")[1]["result"], {"previous": True})
        self.release.set()
        self.wait_job()
        self.assertEqual(self.app.job["status"], "error")
        self.assertEqual(json.loads(previous.read_text()), {"previous": True})
        self.assertEqual(self.app.result, {"previous": True})

    def test_invalid_payload_and_limits(self):
        cases = [[], {}, {**PAYLOAD, "threads": True}, {**PAYLOAD, "threads": 15},
                 {**PAYLOAD, "target": "x" * 65}, {**PAYLOAD, "clean": "x" * 4097},
                 {**PAYLOAD, "output": "secret.txt"}, {**PAYLOAD, "positions": "invalid"}]
        for value in cases:
            with self.subTest(value=value):
                self.assertEqual(self.request("POST", "/api/run", value)[0], 400)
        self.assertEqual(self.request("POST", "/api/run", raw=b"{")[0], 400)
        self.assertEqual(self.request("POST", "/api/run", raw=b"x" * 32769)[0], 413)
        self.assertEqual(self.request("POST", "/api/run", PAYLOAD,
                                      headers={"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.commands, [])

    def test_cross_origin_host_and_traversal(self):
        self.assertEqual(self.request("POST", "/api/run", PAYLOAD,
                                      headers={"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.request("GET", "/api/state", headers={"Host": "evil.example"})[0], 403)
        for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/..%5csecret.txt", "/secret.txt"):
            with self.subTest(path=path):
                self.assertIn(self.request("GET", path)[0], (403, 404))
        local_origin = f"http://127.0.0.1:{self.server.server_port}"
        self.assertEqual(self.request("POST", "/api/repository", {},
                                      headers={"Origin": local_origin})[0], 202)
        self.wait_job()


if __name__ == "__main__":
    unittest.main()
