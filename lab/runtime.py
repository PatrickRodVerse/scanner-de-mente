"""CPU eager execution with explicit memory limits for a 16 GB notebook."""

import json
import os
from pathlib import Path

MODEL = "openai-community/gpt2"
REVISION = "607a30d783dfa663caf39e06633721c8d4cfcd7e"
ROOT = Path(__file__).resolve().parents[1]


def check_memory(min_gib=3.0):
    import psutil

    available = psutil.virtual_memory().available / 1024**3
    if available < min_gib:
        raise RuntimeError(
            f"Available RAM: {available:.2f} GiB. Required: {min_gib:.1f} GiB. "
            "Close other apps and try again. No model was loaded."
        )
    return available


def configure(threads=4):
    if not 1 <= threads <= 14:
        raise ValueError("threads must be between 1 and 14")
    os.environ.setdefault("HF_HOME", str(ROOT / ".cache" / "huggingface"))
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    import torch

    torch.set_num_threads(threads)
    torch.manual_seed(0)


def download_model():
    os.environ.setdefault("HF_HOME", str(ROOT / ".cache" / "huggingface"))
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import LocalEntryNotFoundError

    files = ["config.json", "model.safetensors", "tokenizer.json",
             "tokenizer_config.json", "vocab.json", "merges.txt"]
    try:
        cached = snapshot_download(MODEL, revision=REVISION, local_files_only=True)
        if all((Path(cached) / name).is_file() for name in files):
            return cached
    except LocalEntryNotFoundError:
        pass

    return snapshot_download(
        MODEL,
        revision=REVISION,
        allow_patterns=files,
        max_workers=1,
    )


def load_model(threads=4):
    check_memory()
    configure(threads)
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model_path = download_model()
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_path, local_files_only=True, use_safetensors=True,
        torch_dtype=torch.float32, attn_implementation="eager",
    ).eval()
    model.requires_grad_(False)
    model.config.use_cache = False
    return model, tokenizer


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False),
                         encoding="utf-8")
    temporary.replace(path)


if __name__ == "__main__":
    import argparse
    import psutil

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="Download the model weights and tokenizer")
    args = parser.parse_args()
    print(f"Available RAM: {psutil.virtual_memory().available / 1024**3:.2f} GiB")
    print(f"Free disk space: {psutil.disk_usage(str(ROOT)).free / 1024**3:.1f} GiB")
    if args.download:
        print(download_model())
    else:
        try:
            check_memory()
        except RuntimeError as error:
            parser.exit(2, str(error) + "\n")
