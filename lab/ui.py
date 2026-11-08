"""Local browser interface; model execution stays in a separate, bounded job."""

import argparse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
from urllib.parse import unquote, urlsplit
import uuid

from .runtime import MODEL, REVISION, ROOT


GRAPHIFY_UNAVAILABLE = (
    "Graphify is unavailable. Install graphifyy in a Python environment, then restart the lab "
    "with --graphify-python pointing to that environment's Python executable."
)


def _graphify_supported(python, root):
    try:
        probe = subprocess.run(
            [python, "-c", "from graphify.build import build_from_json; from graphify.export import to_html, to_json"],
            cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env={**os.environ, "PYTHONSAFEPATH": "1"}, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return probe.returncode == 0
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False


def memory_snapshot():
    import psutil

    memory = psutil.virtual_memory()
    available, total = memory.available / 1024**3, memory.total / 1024**3
    return {"available_gib": available, "total_gib": total,
            "minimum_gib": 3, "can_run": available >= 3}


def _read_json(path, expected):
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        return result if isinstance(result, expected) else None
    except (OSError, ValueError):
        return None


def validate_run(payload):
    if not isinstance(payload, dict) or set(payload) - {
            "clean", "corrupt", "target", "contrast", "positions", "threads"}:
        raise ValueError("The request must be a JSON object with recognized fields.")
    values = dict(payload)
    for field, limit in (("clean", 4096), ("corrupt", 4096), ("target", 64), ("contrast", 64)):
        value = values.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
            raise ValueError(f"{field} must contain between 1 and {limit} characters.")
    if values["clean"] == values["corrupt"] or values["target"] == values["contrast"]:
        raise ValueError("The two prompts must differ, and target and contrast must differ.")
    values.setdefault("positions", "changed,last")
    values.setdefault("threads", 4)
    if values["positions"] not in ("all", "changed,last"):
        raise ValueError("positions must be all or changed,last.")
    if type(values["threads"]) is not int or not 1 <= values["threads"] <= 14:
        raise ValueError("threads must be an integer between 1 and 14.")
    return values


class LabApplication:
    def __init__(self, root=ROOT, graphify_python=sys.executable, *, runner=None, memory_reader=None):
        self.root = Path(root).resolve()
        self.graphify_python = str(graphify_python)
        self.graphify_available = runner is not None or _graphify_supported(self.graphify_python, self.root)
        self.memory_reader = memory_reader or memory_snapshot
        self.runner = runner or self._run_command
        self.lock = threading.RLock()
        self.job = {"id": None, "kind": None, "status": "idle", "error": None, "warning": None}
        self.log = deque(maxlen=200)
        self.result = _read_json(self.root / "artifacts/patching.json", dict)
        self.process = None

    def _log(self, line):
        with self.lock:
            self.log.append(str(line).rstrip()[:4096])

    def current_result(self):
        with self.lock:
            if self.job["status"] != "running":
                saved = _read_json(self.root / "artifacts/patching.json", dict)
                if saved is not None:
                    self.result = saved
            return self.result

    def circuit_available(self):
        try:
            graph = self.root / "artifacts/circuit/graph.html"
            return graph.is_file() and graph.stat().st_mtime_ns >= (
                self.root / "artifacts/patching.json").stat().st_mtime_ns
        except OSError:
            return False

    def state(self):
        repository = _read_json(self.root / "graphify-out/graph.json", dict) or {}
        with self.lock:
            result = self.current_result()
            circuit_available = self.circuit_available()
            job = {**self.job, "log": list(self.log)}
        return {
            "memory": self.memory_reader(), "job": job, "result": result,
            "circuit": {"available": circuit_available},
            "graphify": {"available": self.graphify_available,
                         "message": None if self.graphify_available else GRAPHIFY_UNAVAILABLE},
            "sae": {"metrics": _read_json(self.root / "artifacts/sae/metrics.json", dict),
                    "features": _read_json(self.root / "artifacts/sae/top_features.json", list) or []},
            "repository": {"available": bool(repository), "nodes": len(repository.get("nodes", [])),
                           "edges": len(repository.get("links", repository.get("edges", [])))},
            "model": {"name": MODEL, "revision": REVISION},
        }

    def start(self, kind, payload=None):
        with self.lock:
            if self.job["status"] == "running":
                return 409, {"error": "Another job is already running."}
            if kind == "patching" and not self.memory_reader()["can_run"]:
                return 503, {"error": "Less than 3 GiB of RAM is available. Close other apps before running the model."}
            if kind == "repository" and not self.graphify_available:
                return 503, {"error": GRAPHIFY_UNAVAILABLE}
            self.job = {"id": uuid.uuid4().hex, "kind": kind, "status": "running", "error": None, "warning": None}
            self.log.clear()
            job = {**self.job, "log": []}
        threading.Thread(target=self._work, args=(kind, payload), daemon=True).start()
        return 202, {"job": job}

    def _run_command(self, command, log):
        with subprocess.Popen(command, cwd=self.root, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)) as process:
            with self.lock:
                self.process = process
            try:
                for line in process.stdout:
                    log(line)
                if process.wait():
                    raise RuntimeError(f"The process exited with code {process.returncode}. See the job log for details.")
            finally:
                with self.lock:
                    self.process = None

    def _graph_command(self):
        return [sys.executable, "-u", "-X", "utf8", "-m", "lab.graphs",
                "--graphify-python", self.graphify_python]

    def _export_circuit(self, result_path, result_timestamp, output):
        self.runner(self._graph_command() + ["--results", str(result_path), "--output", str(output)], self._log)
        graph = output / "graph.html"
        if not graph.is_file():
            raise RuntimeError("Graphify did not produce an experiment graph.")
        if result_path.stat().st_mtime_ns != result_timestamp:
            raise RuntimeError("The measurements changed during export. Run the graph export again for the latest result.")
        destination = result_path.parent / "circuit"
        # Publish the HTML last and associate it with the result revision it represents.
        for source in sorted(output.rglob("*"), key=lambda path: path == graph):
            if not source.is_file():
                continue
            target = destination / source.relative_to(output)
            target.parent.mkdir(parents=True, exist_ok=True)
            staged = target.with_name(target.name + ".tmp")
            shutil.copyfile(source, staged)
            if source == graph:
                os.utime(staged, ns=(result_timestamp, result_timestamp))
            staged.replace(target)

    def _work(self, kind, payload):
        try:
            warning = None
            if kind == "repository":
                self.runner(self._graph_command() + ["--repo", "--output", str(self.root / "graphify-out")], self._log)
            else:
                artifacts = self.root / "artifacts"
                artifacts.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(prefix=".ui-job-", dir=artifacts, ignore_cleanup_errors=True) as temporary:
                    temporary = Path(temporary)
                    result_path = temporary / "patching.json"
                    command = [sys.executable, "-u", "-X", "utf8", "-m", "lab.patching"]
                    command += [f"--{field}={payload[field]}" for field in (
                        "clean", "corrupt", "target", "contrast", "positions", "threads")]
                    self.runner(command + ["--output", str(result_path)], self._log)
                    result = _read_json(result_path, dict)
                    if result is None:
                        raise RuntimeError("The experiment did not produce a valid JSON result.")
                    result_timestamp = result_path.stat().st_mtime_ns
                    published = artifacts / "patching.json"
                    with self.lock:
                        result_path.replace(published)
                        self.result = result
                    if self.graphify_available:
                        try:
                            self._export_circuit(published, result_timestamp, temporary / "circuit")
                        except Exception as error:
                            warning = f"Measurements saved. Graph export failed: {error}"[:2000]
                    else:
                        warning = f"Measurements saved. {GRAPHIFY_UNAVAILABLE}"
            if warning:
                self._log(warning)
            self._log("Job complete.")
            with self.lock:
                self.job.update(status="success", warning=warning)
        except Exception as error:
            self._log(str(error))
            with self.lock:
                self.job.update(status="error", error=str(error)[:2000])

    def close(self):
        with self.lock:
            process = self.process
        if process is not None:
            process.terminate()


def make_server(app, port=8765):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, format, *args):
            pass

        def _drain_small_body(self):
            lengths = self.headers.get_all("Content-Length", [])
            if self.command != "POST" or len(lengths) != 1 or "Transfer-Encoding" in self.headers:
                return
            if lengths[0].isascii() and lengths[0].isdigit():
                length = int(lengths[0])
                if length <= 32768:
                    # Windows may reset a closed connection while its request body remains unread.
                    self.rfile.read(length)

        def _allowed_request(self):
            hosts = self.headers.get_all("Host", [])
            allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if len(hosts) != 1 or hosts[0].lower() not in allowed:
                self._drain_small_body()
                self._json(403, {"error": "Invalid local Host header."})
                return False
            if self.command == "POST":
                origins = self.headers.get_all("Origin", [])
                if origins and (len(origins) != 1 or origins[0] != "http://" + hosts[0]):
                    self._drain_small_body()
                    self._json(403, {"error": "The Origin header must match the local server address."})
                    return False
            return True

        def _send(self, code, content, content_type, *, attachment=False):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "SAMEORIGIN")
            self.send_header("Referrer-Policy", "no-referrer")
            if attachment:
                self.send_header("Content-Disposition", 'attachment; filename="patching.json"')
            self.end_headers()
            try:
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _json(self, code, value, *, attachment=False):
            self._send(code, json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"),
                       "application/json; charset=utf-8", attachment=attachment)

        def _file(self, path, boundary):
            if not path.resolve().is_relative_to(boundary):
                self._json(403, {"error": "Invalid path."})
                return
            try:
                content = path.read_bytes()
            except OSError:
                self._json(404, {"error": "This file is not available yet."})
                return
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            if content_type.startswith("text/") or content_type in ("application/javascript", "application/json"):
                content_type += "; charset=utf-8"
            self._send(200, content, content_type)

        def _path(self):
            parsed = urlsplit(self.path)
            if parsed.scheme or parsed.netloc:
                raise ValueError("Invalid path.")
            path = unquote(parsed.path, errors="strict")
            if "\\" in path or "\0" in path or ".." in path.split("/"):
                raise ValueError("Invalid path.")
            return path

        def do_GET(self):
            if not self._allowed_request():
                return
            try:
                path = self._path()
            except (ValueError, UnicodeError):
                self._json(403, {"error": "Invalid path."})
                return
            if path == "/api/state":
                self._json(200, app.state())
            elif path in ("/api/result", "/api/export"):
                result = app.current_result()
                if result is None:
                    self._json(404, {"error": "No experiment result is available yet."})
                else:
                    self._json(200, result, attachment=path == "/api/export")
            elif path == "/graphs/repository":
                self._file(app.root / "graphify-out/graph.html", app.root / "graphify-out")
            elif path == "/graphs/circuit":
                with app.lock:
                    if app.circuit_available():
                        self._file(app.root / "artifacts/circuit/graph.html", app.root / "artifacts/circuit")
                    else:
                        self._json(404, {"error": "No circuit graph is available for the current result."})
            else:
                static = app.root / "ui"
                target = (static / ("index.html" if path == "/" else path.lstrip("/"))).resolve()
                if not target.is_relative_to(static) or not target.is_file():
                    self._json(404, {"error": "File not found."})
                else:
                    self._file(target, static)

        def do_POST(self):
            if not self._allowed_request():
                return
            try:
                path = self._path()
                lengths = self.headers.get_all("Content-Length", [])
                if len(lengths) != 1 or "Transfer-Encoding" in self.headers:
                    raise ValueError("Exactly one Content-Length header is required, without Transfer-Encoding.")
                length = int(lengths[0])
                if not 0 <= length <= 32768:
                    if length > 0:
                        self.rfile.read(min(length, 32769))
                    self._json(413, {"error": "The JSON body is limited to 32 KiB."})
                    return
                if self.headers.get_content_type() != "application/json":
                    self._drain_small_body()
                    self._json(415, {"error": "Use Content-Type: application/json."})
                    return
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if path == "/api/run":
                    values = validate_run(payload)
                    code, response = app.start("patching", values)
                elif path == "/api/repository":
                    if payload != {}:
                        raise ValueError("The graph request body must be an empty JSON object.")
                    code, response = app.start("repository")
                else:
                    self._json(404, {"error": "Unknown endpoint."})
                    return
                self._json(code, response)
            except (ValueError, UnicodeError, TypeError):
                self._json(400, {"error": "Invalid JSON request or parameters out of range."})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--graphify-python", default=sys.executable, help="Python executable for optional Graphify exports")
    parser.add_argument("--open", action="store_true", help="Open the panel in the default browser")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    address = f"http://127.0.0.1:{args.port}"
    if args.open:
        import urllib.request
        import webbrowser
        try:
            with urllib.request.urlopen(address + "/api/state", timeout=1) as response:
                existing = json.load(response)
            if existing.get("model", {}).get("name") == MODEL:
                webbrowser.open(address)
                return
        except (OSError, ValueError):
            pass
    app = LabApplication(graphify_python=args.graphify_python)
    server = make_server(app, args.port)
    print(f"Local lab: http://127.0.0.1:{server.server_port}", flush=True)
    if args.open:
        threading.Timer(0.3, webbrowser.open, args=(f"http://127.0.0.1:{server.server_port}",)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.close()
        server.server_close()


if __name__ == "__main__":
    main()
