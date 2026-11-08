"""Build the Windows installer with its own Python and pinned CPU dependencies."""

import argparse
import hashlib
from importlib import metadata
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PYTHON_VERSION = (3, 11, 15)


def locked_packages():
    return dict(line.split("==", 1) for line in
                (ROOT / "requirements-windows.lock").read_text(encoding="utf-8").splitlines()
                if line and not line.startswith("#"))


def copy_dependencies(destination):
    # Copy wheel-owned files only, never the developer's entire environment.
    for name, expected in locked_packages().items():
        distribution = metadata.distribution(name)
        if distribution.version != expected:
            raise ValueError(f"{name}: expected {expected}, installed {distribution.version}")
        origin = Path(distribution.locate_file("")).resolve()
        for entry in distribution.files or ():
            source = Path(distribution.locate_file(entry))
            if (source.suffix in (".pyc", ".pyo", ".pth") or
                    source.name == "direct_url.json" or "__pycache__" in source.parts):
                continue
            resolved = source.resolve()
            if not resolved.is_relative_to(origin):
                continue  # Wheel console scripts are not needed by the application.
            if source.is_symlink() or not source.is_file():
                raise ValueError(f"Missing or symlinked dependency file: {source}")
            target = destination / resolved.relative_to(origin)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def prepare_payload(destination):
    base = Path(sys.base_prefix)
    runtime = destination / "runtime"
    runtime.mkdir(parents=True)
    for name in ("python.exe", "pythonw.exe", "python3.dll", "python311.dll",
                 "vcruntime140.dll", "vcruntime140_1.dll", "LICENSE.txt"):
        shutil.copy2(base / name, runtime / name)
    for name in ("DLLs", "Lib"):
        shutil.copytree(base / name, runtime / name,
                        ignore=shutil.ignore_patterns("site-packages", "__pycache__", "*.pyc", "*.pyo"))
    copy_dependencies(runtime / "Lib/site-packages")
    # Fixed relative paths keep child workers independent of installed Python and PATH.
    (runtime / "python311._pth").write_text(
        ".\nDLLs\nLib\nLib/site-packages\n..\nimport site\n", encoding="utf-8")
    for name in ("lab", "ui"):
        shutil.copytree(ROOT / name, destination / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
    for name in ("LICENSE", "INSTALL.md", "README.md", "THIRD-PARTY-NOTICES.md",
                 "requirements-windows.lock"):
        shutil.copy2(ROOT / name, destination / name)
    (destination / "RUNTIME-VERSIONS.txt").write_text(
        "Python " + ".".join(map(str, PYTHON_VERSION)) + "\n" +
        "\n".join(f"{name}=={pin}" for name, pin in locked_packages().items()) + "\n",
        encoding="utf-8")
    subprocess.run([str(runtime / "python.exe"), "-B", "-c",
                    "import ssl, sqlite3, torch, transformers, psutil; "
                    "from transformers import GPT2LMHeadModel; import lab.ui; "
                    "assert torch.__version__ == '2.10.0+cpu'; "
                    "assert torch.version.cuda is None; print('Relocated runtime imports: OK')"],
                   cwd=destination.parent, check=True, timeout=120)


def verified_redist():
    path = ROOT / ".cache/windows-build/vc_redist.x64.exe"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with urllib.request.urlopen("https://aka.ms/vc14/vc_redist.x64.exe", timeout=60) as response:
            with path.with_suffix(".download").open("wb") as output:
                shutil.copyfileobj(response, output)
        path.with_suffix(".download").replace(path)
    quoted = str(path).replace("'", "''")
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    subprocess.run([str(powershell), "-NoProfile", "-NonInteractive", "-Command",
                    "Import-Module (Join-Path $PSHOME "
                    "'Modules/Microsoft.PowerShell.Security/Microsoft.PowerShell.Security.psd1') "
                    "-ErrorAction Stop; "
                    f"$s = Get-AuthenticodeSignature -LiteralPath '{quoted}' -ErrorAction Stop; "
                    "if ($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notlike "
                    "'*Microsoft Corporation*') { throw 'Invalid Microsoft runtime signature' }"],
                   check=True, timeout=120)
    return path


def compiler_path(explicit):
    candidates = [explicit, shutil.which("ISCC.exe")]
    for variable in ("LOCALAPPDATA", "ProgramFiles", "ProgramFiles(x86)"):
        prefix = Path(os.environ.get(variable, "C:/"))
        candidates.extend((prefix / "Programs/Inno Setup 7/ISCC.exe", prefix / "Inno Setup 7/ISCC.exe"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    raise FileNotFoundError("Install Inno Setup 7, or pass --iscc with its ISCC.exe path.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iscc", type=Path)
    parser.add_argument("--version", default="0.1.0")
    args = parser.parse_args()
    if sys.platform != "win32" or struct.calcsize("P") != 8 or sys.version_info[:3] != PYTHON_VERSION:
        parser.error("Build using 64-bit CPython 3.11.15 and requirements-windows.lock.")
    if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        parser.error("version must contain three numeric components")
    compiler = compiler_path(args.iscc)
    redist = verified_redist()
    build = ROOT / "build/windows"
    build.mkdir(parents=True, exist_ok=True)
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="app-", dir=build, ignore_cleanup_errors=True) as temporary:
        payload = Path(temporary)
        prepare_payload(payload)
        subprocess.run([str(compiler), f"/DAppSource={payload}", f"/DRedistPath={redist}",
                        f"/DOutputDir={output}", f"/DAppVersion={args.version}",
                        str(ROOT / "scripts/windows-installer.iss")], check=True)
    installer = output / "Scanner-de-Mente-Setup-x64.exe"
    with installer.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    (output / "SHA256SUMS.txt").write_text(f"{digest}  {installer.name}\n", encoding="ascii")
    print(f"Built {installer} ({installer.stat().st_size / 1024**2:.1f} MiB)")


if __name__ == "__main__":
    main()
