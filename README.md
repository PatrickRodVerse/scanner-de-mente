# Scanner de Mente

An interactive activation patching lab for GPT‑2 Small. Explore how swapping an
internal state changes which of two names the model favors, then run the same
kind of intervention on your own prompts.

The [web study](site/index.html) replays CPU measurements from 24 interventions
and four prompt comparisons. The [local lab](INSTALL.md) runs GPT‑2 on your computer.

## Install and run your own experiments

**[Download the Windows installer (.exe)](https://github.com/PatrickRodVerse/scanner-de-mente/releases/latest/download/Scanner-de-Mente-Setup-x64.exe)**

1. Download and run `Scanner-de-Mente-Setup-x64.exe` on Windows 10 or 11 x64.
2. Open **Scanner de Mente** from the Start menu or desktop shortcut.
3. Run the example, then edit both prompts and the two answer candidates. Inspect the heatmap and export the result as JSON.

The installer includes Python and pinned CPU dependencies. No separate Python
installation or ZIP extraction is required. It installs for the current user,
creates shortcuts, and registers an uninstaller. If the Microsoft Visual C++
runtime is missing, its installer requests administrator approval.

The first experiment downloads the pinned GPT‑2 checkpoint (about 550 MB) and
needs at least 3 GiB of available RAM. The application opens in your browser;
experiments run locally. Keep its console open and close it to stop the server.
Graphify adds optional graph exports. See [INSTALL.md](INSTALL.md) for details.

The repository's **Code → Download ZIP** contains source code. The application
installer is the `.exe` in [Releases](https://github.com/PatrickRodVerse/scanner-de-mente/releases).
The installer is unsigned; its SHA-256 checksum is published with the release.

## Source code and license

Original project code is available under the [MIT license](LICENSE).
Bundled dependencies retain their [own licenses](THIRD-PARTY-NOTICES.md).
To run a source checkout, install 64-bit Python 3.11 and open
`scripts/install-lab.cmd`. This developer path creates a local `.venv`.

## Build the Windows installer

On Windows x64, install [uv](https://docs.astral.sh/uv/getting-started/installation/)
and [Inno Setup 7.1.1](https://jrsoftware.org/isdl.php), then run:

```powershell
uv python install 3.11.15
uv venv --python 3.11.15 .venv
uv pip sync requirements-windows.lock --extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match
.venv\Scripts\python.exe scripts/build_windows.py
.venv\Scripts\python.exe scripts/check_windows_install.py dist/Scanner-de-Mente-Setup-x64.exe
```

The build copies wheel-owned dependency files and a private Python runtime;
developer caches, model weights, and experiment results are excluded. It checks
the Microsoft runtime's publisher signature before bundling it. Output is in
`dist/`, along with `SHA256SUMS.txt`. The Windows release workflow builds and
checks the installer again; version tags publish the `.exe` as a release asset.

## Reproduce the study

The archived [measurements](site/ioi.json) contain the checkpoint revision,
prompt pairs, matched controls, and scores. After installing the lab, run this
command from its root to write a separate reproduction file.

```powershell
.venv\Scripts\python.exe -m lab.ioi_case --output artifacts/reference-ioi.json
```

In the John and Mary example, restoring the changed name had an effect of +5.08
logits. Holding the final token's state fixed reduced that effect to +0.95 logits.
Holding the neighbor fixed preserved almost all of it. The interventions operate
on whole activation vectors. Which attention heads and paths carry the effect
remains an open question. [Related GPT‑2 research](https://arxiv.org/abs/2211.00593)

## Preview and publish

From the repository root, serve the English study.

```powershell
python -m http.server 8766 --bind 127.0.0.1 --directory site
```

Open <http://127.0.0.1:8766/>. On GitHub, choose **Settings → Pages → GitHub Actions**
and run **Publish Scanner de Mente**. The workflow uploads `site/`; its install
button downloads the `.exe` from the latest GitHub release.
[GitHub Pages workflow guide](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)

For project history, see the [Portuguese lab notes](docs/LAB-NOTES-PT.md) and the
[collaboration record](docs/AI-COLLABORATION.md).
