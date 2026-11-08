"""Activation patching by block and position for the next-token IOI metric."""

import argparse
import time
from pathlib import Path

from .runtime import MODEL, REVISION, load_model, write_json

CLEAN = "When John and Mary went to the shops, John gave the bag to"
CORRUPT = "When John and Mary went to the shops, Mary gave the bag to"


def recovery(score, clean, corrupt):
    gap = clean - corrupt
    return None if abs(gap) < 1e-4 else (score - corrupt) / gap


def prepare_pair(tokenizer, clean, corrupt, target, contrast):
    target_ids = tokenizer.encode(" " + target, add_special_tokens=False)
    contrast_ids = tokenizer.encode(" " + contrast, add_special_tokens=False)
    if len(target_ids) != 1 or len(contrast_ids) != 1 or target_ids == contrast_ids:
        raise ValueError("Target and contrast must each encode as one distinct token with a leading space.")
    ids = tokenizer(clean, return_tensors="pt")["input_ids"]
    other = tokenizer(corrupt, return_tensors="pt")["input_ids"]
    if ids.shape != other.shape or not 2 <= ids.shape[1] <= 64:
        raise ValueError("Both prompts must have the same length, between 2 and 64 tokens.")
    changed = (ids[0] != other[0]).nonzero().flatten().tolist()
    if not changed:
        raise ValueError("The prompts must differ in at least one token.")
    return ids, other, target_ids[0], contrast_ids[0], changed


def experiment(model, tokenizer, clean=CLEAN, corrupt=CORRUPT, target="Mary", contrast="John",
               positions="changed,last"):
    import torch
    from .hooks import capture, patch

    ids, other, target_id, contrast_id, changed = prepare_pair(
        tokenizer, clean, corrupt, target, contrast)
    blocks = model.transformer.h
    last_layer, last_pos = len(blocks) - 1, ids.shape[1] - 1
    null_position = next((position for position in changed if position < last_pos), 0)
    selected = list(range(ids.shape[1])) if positions == "all" else sorted(set(changed + [last_pos]))

    def score(tokens):
        logits = model(tokens, use_cache=False).logits[0, -1]
        return (logits[target_id] - logits[contrast_id]).item()

    started = time.perf_counter()
    with torch.inference_mode():
        with capture(blocks) as clean_states:
            clean_score = score(ids)
        with capture(blocks, [last_layer]) as corrupt_states:
            corrupt_score = score(other)
        with patch(blocks[last_layer], last_pos, corrupt_states[last_layer][:, last_pos]):
            identity = score(other)
        with patch(blocks[last_layer], last_pos, clean_states[last_layer][:, last_pos]):
            final_restore = score(other)
        with patch(blocks[last_layer], null_position, clean_states[last_layer][:, null_position]):
            structural_null = score(other)
        with patch(blocks[last_layer], last_pos, clean_states[last_layer][:, last_pos]):
            clean_identity = score(ids)
        controls = {"corrupt_identity_error": abs(identity - corrupt_score),
                    "clean_identity_error": abs(clean_identity - clean_score),
                    "final_restore_error": abs(final_restore - clean_score),
                    "final_nonlast_effect": structural_null - corrupt_score,
                    "final_nonlast_position": null_position,
                    "final_restore_recovery": recovery(final_restore, clean_score, corrupt_score)}
        if any(abs(controls[key]) > 1e-4 for key in (
                "corrupt_identity_error", "clean_identity_error", "final_restore_error",
                "final_nonlast_effect")):
            raise RuntimeError(f"Patching controls failed: {controls}")
        patches = []
        for layer in range(len(blocks)):
            for position in selected:
                with patch(blocks[layer], position, clean_states[layer][:, position]):
                    patched_score = score(other)
                patches.append({"layer": layer, "position": position,
                                "patched_score": patched_score,
                                "effect": patched_score - corrupt_score,
                                "recovery": recovery(patched_score, clean_score, corrupt_score)})
            print(f"Block {layer + 1}/{len(blocks)} complete", flush=True)
        norms = [clean_states[i][0].norm(dim=-1).tolist() for i in range(len(blocks))]
    import psutil
    return {"model": MODEL, "revision": REVISION, "clean_prompt": clean,
            "corrupt_prompt": corrupt, "target": target, "contrast": contrast,
            "tokens": [tokenizer.decode([token]) for token in ids[0].tolist()],
            "clean_score": clean_score, "corrupt_score": corrupt_score,
            "denominator": clean_score - corrupt_score, "controls": controls,
            "activation_norms": norms, "patches": patches,
            "metadata": {"device": "cpu", "dtype": "float32", "threads": torch.get_num_threads(),
                         "elapsed_seconds": time.perf_counter() - started,
                         "rss_mib_at_end": psutil.Process().memory_info().rss / 1024**2,
                         "positions": selected, "changed_positions": changed,
                         "baseline_task_passed": clean_score > 0 and corrupt_score < 0,
                         "interpretation": "Measured local effect on the next-token score for this prompt pair."}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--positions", choices=["all", "changed,last"], default="changed,last")
    parser.add_argument("--clean", default=CLEAN)
    parser.add_argument("--corrupt", default=CORRUPT)
    parser.add_argument("--target", default="Mary")
    parser.add_argument("--contrast", default="John")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("artifacts/patching.json"))
    args = parser.parse_args()
    try:
        model, tokenizer = load_model(args.threads)
    except RuntimeError as error:
        parser.exit(2, str(error) + "\n")
    result = experiment(model, tokenizer, args.clean, args.corrupt, args.target,
                        args.contrast, args.positions)
    write_json(args.output, result)
    print(f"Clean logit difference: {result['clean_score']:.4f}. Corrupted: {result['corrupt_score']:.4f}.")
    print(f"Result: {args.output.resolve()}")
    if not result["metadata"]["baseline_task_passed"]:
        print("Warning: the model did not predict the expected answer for both prompts. Interpret the measured effects in this context.")
    if abs(result["denominator"]) < 1e-4:
        print("Warning: normalized recovery is unavailable because the baseline gap is too small.")


if __name__ == "__main__":
    main()
