# Install Scanner de Mente

Scanner de Mente is a local browser lab for **activation patching** in GPT-2 Small. Choose two short prompts, copy an internal state from one run into the other, and measure how the model's preference between two next-token candidates changes. The heatmap shows which layer and token positions were tested. Export the prompts, model revision, controls, and scores as JSON to share or reproduce a run.

## Windows quick start

1. Download [Scanner-de-Mente-Setup-x64.exe](https://github.com/PatrickRodVerse/scanner-de-mente/releases/latest/download/Scanner-de-Mente-Setup-x64.exe) from GitHub Releases. Requires Windows 10 or 11 x64.
2. Run the installer. Python and the CPU dependencies are included. If Microsoft's Visual C++ runtime is missing or outdated, approve the Microsoft runtime installer when Windows asks. Restart if requested, then run setup again.
3. Open **Scanner de Mente** from the Start menu. A desktop shortcut is optional during setup. Keep the console window open; closing it stops the local server. Open [the local lab](http://127.0.0.1:8765/) if the browser does not open on its own.

The app installs under `%LOCALAPPDATA%\Programs\Scanner de Mente` for the current user, with its own runtime. It does not require an existing Python installation. Installing the app and opening its interface work offline; the first experiment needs internet to download the pinned GPT-2 Small checkpoint and tokenizer from Hugging Face (about 550 MB). Allow a few gigabytes of disk space and at least 3 GiB of available RAM to run the model. Experiments and prompts stay on your computer.

Uninstall through Windows Settings or the Start menu uninstaller. Generated results in `artifacts` and downloaded models in `.cache` are preserved. Export results before uninstalling. The installer is unsigned; compare its SHA-256 hash with `SHA256SUMS.txt` on the release page. The GitHub **Download ZIP** option provides the source code, not the installer.

## Run a source checkout

For development, install [64-bit Python 3.11 for Windows](https://www.python.org/downloads/windows/), then open `scripts/install-lab.cmd` from the complete source checkout or source bundle. This creates `.venv`, installs the pinned dependencies, and starts the same local lab. To return later, run the launcher again.

## Run your own test

1. Run the prefilled John and Mary example to see the baseline, controls, and intervention heatmap.
2. Edit the two prompts and the two completion candidates. Each prompt must contain 2–64 GPT-2 tokens, and both must contain the same number of tokens. Change at least one token. Each candidate must be a different single GPT-2 token when prefixed with a space. Start by changing one name and keeping the rest of the sentence fixed.
3. Run the experiment and select a heatmap cell. The logit difference compares the two candidates. Recovery compares the patched difference with the clean and changed baselines. A patch measures the effect of copying that state for this prompt pair.
4. Export the result as JSON. To regenerate the measurements used in the public study from the lab folder, run:

   ```powershell
   .\.venv\Scripts\python.exe -m lab.ioi_case --output artifacts/reference-ioi.json
   ```

If port 8765 is in use by another application, open PowerShell in the installed app folder and run `.\runtime\python.exe -B -m lab.ui --port 8767 --open` (use `.venv\Scripts\python.exe` in a source checkout). Graphify is optional for graph exports. The experiment, heatmap, and JSON export run with the base installation.

## Manual setup on Linux or macOS

The following commands use Python 3.11 and the same pinned requirements. The application installer is for Windows x64. Linux and Apple silicon macOS commands are provided for manual setup.

```sh
python3.11 -m venv .venv
```

On Linux, install the CPU PyTorch wheel first:

```sh
.venv/bin/python -m pip install --index-url https://download.pytorch.org/whl/cpu 'torch==2.10.0+cpu'
```

On Apple silicon macOS, PyTorch comes from the default index with the other requirements. On either platform, continue with:

```sh
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
.venv/bin/python -m lab.ui --open
```

See the [PyTorch 2.10.0 installation matrix](https://pytorch.org/get-started/previous-versions/#v2100) for platform wheel details.
