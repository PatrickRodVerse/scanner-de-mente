"""Build the local lab download from source files only."""

import argparse
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]


def build_bundle(output):
    files = [ROOT / path for path in (
        "README.md", "INSTALL.md", "LICENSE", "THIRD-PARTY-NOTICES.md",
        "requirements.txt", "scripts/install-lab.cmd",
        "ui/index.html", "ui/style.css", "ui/app.js", "ui/fonts/fonts.css",
    )]
    files.extend(sorted((ROOT / "lab").glob("*.py")))
    files.extend(sorted((ROOT / "ui/fonts").glob("*.woff2")))
    files.extend(sorted((ROOT / "ui/fonts").glob("*-OFL.txt")))
    for path in files:
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(ROOT):
            raise ValueError(f"Missing or external bundle input: {path.relative_to(ROOT)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=output.parent, suffix=".zip", delete=False) as temp:
        temporary = Path(temp.name)
    try:
        with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as bundle:
            for path in files:
                bundle.write(path, "scanner-de-mente-lab/" + path.relative_to(ROOT).as_posix())
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Built {output} with {len(files)} source files.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "site/scanner-de-mente-lab.zip")
    build_bundle(parser.parse_args().output)
