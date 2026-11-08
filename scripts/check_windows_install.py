"""Install, exercise and uninstall the actual Windows release in a temporary folder."""

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
import winreg

UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ScannerDeMente_is1"


def registered():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY):
            return True
    except FileNotFoundError:
        return False


def run_hidden(command, **kwargs):
    return subprocess.run(command, check=True, creationflags=subprocess.CREATE_NO_WINDOW,
                          timeout=600, **kwargs)


def check_runtime(app, outside):
    python = app / "runtime/python.exe"
    environment = {key: value for key, value in os.environ.items()
                   if key.upper() not in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV")}
    environment["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
    code = """
import json, pathlib, subprocess, sys
import psutil, torch, transformers
from transformers import GPT2Config, GPT2LMHeadModel
from lab.hooks import capture, patch
from lab.runtime import ROOT
assert sys.flags.isolated and sys.flags.ignore_environment
assert pathlib.Path(sys.prefix).resolve() == pathlib.Path(sys.executable).parent.resolve()
assert torch.__version__ == '2.10.0+cpu' and torch.version.cuda is None
assert transformers.__version__ == '4.57.6'
torch.set_num_threads(1)
torch.manual_seed(0)
model = GPT2LMHeadModel(GPT2Config(vocab_size=32, n_positions=8, n_embd=16,
    n_layer=2, n_head=2, attn_pdrop=0, resid_pdrop=0, embd_pdrop=0)).eval()
clean, changed = torch.tensor([[1, 2, 3]]), torch.tensor([[4, 4, 5]])
with torch.inference_mode():
    with capture(model.transformer.h) as states:
        expected = model(clean, use_cache=False).logits[:, -1]
    with patch(model.transformer.h[-1], -1, states[1][:, -1]):
        restored = model(changed, use_cache=False).logits[:, -1]
    torch.testing.assert_close(restored, expected)
assert all(not block._forward_hooks for block in model.transformer.h)
subprocess.run([sys.executable, '-B', '-m', 'lab.patching', '--help'], check=True,
               cwd=ROOT, stdout=subprocess.DEVNULL, timeout=60)
print(json.dumps({'python': sys.version.split()[0], 'torch': torch.__version__,
                 'tiny_gpt2_patching': 'passed', 'child_worker': 'passed'}))
"""
    run_hidden([str(python), "-B", "-c", code], cwd=outside, env=environment)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    address = f"http://127.0.0.1:{port}"
    with (outside / "server.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen([str(python), "-B", "-X", "utf8", "-m", "lab.ui", "--port", str(port)],
                                   cwd=outside, env=environment, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            deadline = time.monotonic() + 45
            while True:
                try:
                    with urllib.request.urlopen(address + "/api/state", timeout=2) as response:
                        state = json.load(response)
                    break
                except (OSError, ValueError):
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("Installed server failed; see " + str(outside / "server.log"))
                    time.sleep(0.25)
            assert state["model"]["name"] == "openai-community/gpt2", state
            assert state["job"]["status"] == "idle", state
            assert not state["graphify"]["available"], state
            for path, content in (("/", b"Scanner de Mente"), ("/app.js", b"patchIndex"),
                                  ("/fonts/fonts.css", b"font-face")):
                with urllib.request.urlopen(address + path, timeout=3) as response:
                    assert content in response.read(), path
            request = urllib.request.Request(address + "/api/run", data=b"{}",
                                             headers={"Content-Type": "application/json"})
            try:
                urllib.request.urlopen(request, timeout=3)
                raise AssertionError("The installed API accepted an invalid experiment")
            except urllib.error.HTTPError as error:
                assert error.code == 400, error
            print("Installed local API, assets, input validation and optional Graphify: passed")
        finally:
            process.terminate()
            process.wait(timeout=15)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("installer", type=Path)
    args = parser.parse_args()
    installer = args.installer.resolve(strict=True)
    if registered():
        parser.error("Scanner de Mente is already registered. Test on a separate Windows user or CI runner.")
    group = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Scanner de Mente"
    if group.exists():
        parser.error("The Scanner de Mente Start menu folder already exists. Use a separate Windows user or CI runner.")
    reports = Path(__file__).resolve().parents[1] / ".cache/windows-build"
    reports.mkdir(parents=True, exist_ok=True)
    identifier = uuid.uuid4().hex
    install_log, uninstall_log = (reports / f"{kind}-{identifier}.log" for kind in ("install", "uninstall"))
    with tempfile.TemporaryDirectory(prefix="Scanner instala\u00e7\u00e3o ") as temporary:
        root = Path(temporary).resolve()
        app = root / "Installed app"
        assert app.is_relative_to(root)
        shortcut = group / "Scanner de Mente.lnk"
        uninstaller = app / "unins000.exe"
        try:
            run_hidden([str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-",
                        f"/DIR={app}", "/TASKS=", f"/LOG={install_log}"])
            assert registered(), "The installer did not register the app"
            assert uninstaller.is_file(), "The uninstaller is missing"
            assert shortcut.is_file(), "The Start menu shortcut is missing"
            for relative in ("artifacts/keep-result.json", ".cache/keep-model.txt"):
                fixture = app / relative
                fixture.parent.mkdir(parents=True, exist_ok=True)
                fixture.write_text("keep this user data", encoding="utf-8")
            check_runtime(app, root)
        finally:
            if uninstaller.is_file():
                run_hidden([str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                            f"/LOG={uninstall_log}"])
                # Inno's launcher can return before its temporary uninstaller finishes.
                deadline = time.monotonic() + 60
                while (registered() or uninstaller.exists() or not uninstall_log.is_file() or
                       "Log closed." not in uninstall_log.read_text(encoding="utf-8-sig", errors="replace")):
                    if time.monotonic() > deadline:
                        raise RuntimeError(f"Uninstall did not finish. See {uninstall_log}")
                    time.sleep(0.25)
        assert not registered(), "The uninstaller left its registration behind"
        assert not shortcut.exists(), "The uninstaller left its shortcut behind"
        assert not (app / "runtime/python.exe").exists(), "The runtime was not removed"
        for relative in ("artifacts/keep-result.json", ".cache/keep-model.txt"):
            assert (app / relative).read_text(encoding="utf-8") == "keep this user data", relative
        print("Actual EXE installation, Start menu shortcut, runtime, uninstall and data preservation: passed")


if __name__ == "__main__":
    main()
