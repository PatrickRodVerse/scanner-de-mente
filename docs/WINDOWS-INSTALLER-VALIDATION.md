# Windows installer validation — 2026-11-08

Built `Scanner-de-Mente-Setup-x64.exe` version 0.1.0 with Inno Setup 7.1.1,
CPython 3.11.15 x64 and `requirements-windows.lock`. The local build is
156,306,834 bytes (149.1 MiB). Its SHA-256 is:

`24bb50f495fe43e0667502da3fe2364add6b581a49a3bdb769009af7fcf362c2`

The checksum of a separately rebuilt release may differ; use the checksum
published alongside that release's installer.

The actual EXE passed `scripts/check_windows_install.py` on Windows x64:

- Installed into a temporary directory containing spaces and non-ASCII text.
- Registered the app and generated the Start menu shortcut and uninstaller.
- Used its bundled runtime from an unrelated working directory, with system
  Python removed from PATH and Python environment overrides cleared.
- Imported the CPU dependencies; ran a tiny randomly initialized GPT-2 model
  through activation restoration; verified child module execution.
- Served the local API and interface assets; rejected invalid experiment input;
  handled missing optional Graphify without disabling the lab.
- Uninstalled the runtime and shortcut, removed its registration, and preserved
  generated result/cache fixtures. The temporary fixtures were then cleaned up.

Existing checks: 20 Python tests completed (19 passed; one optional Graphify
integration test skipped), and both Node data self-checks passed. The public
source set was checked for common credential patterns, sensitive filenames,
symlinks and unexpected large files; no matches were found. Caches, environments,
model weights, generated results and build products are excluded from Git.

The first installer check looked for a custom Start menu group. Inno ignores
`/GROUP` when the group page is disabled; the shortcut was correctly created in
the default group. The checker was corrected and the full test passed.

Not checked: a clean Windows machine lacking the Microsoft VC++ runtime,
its elevation/reboot flow, Linux/macOS installation, or the full pretrained GPT-2
experiment in this session (available RAM was below the 3 GiB guard). The model
test used a tiny random GPT-2, not the pretrained checkpoint. The application
installer is not digitally signed; the bundled Microsoft prerequisite's publisher
signature was verified before packaging.
