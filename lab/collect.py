"""Cache activations from one layer for an SAE, using one UTF-8 sentence per line."""

import argparse
from pathlib import Path

from .runtime import MODEL, REVISION, load_model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--layer", type=int, default=7)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--output", type=Path, default=Path("artifacts/sae-cache.pt"))
    args = parser.parse_args()
    if not 0 <= args.layer < 12 or not 64 <= args.max_tokens <= 32768:
        parser.error("layer: 0..11; max-tokens: 64..32768")
    if not args.corpus.is_file() or args.corpus.stat().st_size > 4 * 1024**2:
        parser.error("Corpus must be a local UTF-8 file of at most 4 MiB")
    lines = list(dict.fromkeys(x.strip() for x in args.corpus.read_text(encoding="utf-8-sig").splitlines() if x.strip()))
    if len(lines) < 4:
        parser.error("Use at least four distinct sentences. Hundreds are recommended.")
    import torch
    from .hooks import capture

    model, tokenizer = load_model()
    vectors, contexts, groups = [], [], []
    total = 0
    with torch.inference_mode():
        for line in lines:
            ids = tokenizer(line, return_tensors="pt", truncation=True, max_length=64)["input_ids"]
            with capture(model.transformer.h, [args.layer]) as states:
                model(ids, use_cache=False)
            count = min(ids.shape[1], args.max_tokens - total)
            vectors.append(states[args.layer][0, :count].clone())
            # The prefix contains only text visible to the model at that position.
            contexts.extend(tokenizer.decode(ids[0, :pos + 1]) for pos in range(count))
            groups.extend([line] * count)
            total += count
            if total >= args.max_tokens:
                break
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"activations": torch.cat(vectors), "contexts": contexts, "groups": groups, "model": MODEL,
                "revision": REVISION, "layer": args.layer}, args.output)
    print(f"Cache: {total} tokens × 768; {args.output.resolve()}")
    print("Features require validation across varied text and interventions.")


if __name__ == "__main__":
    main()
