"""Reproduce the Scanner de Mente IOI study with the pinned GPT-2 checkpoint."""

import argparse
import math
from pathlib import Path

from .hooks import capture, patch
from .patching import CLEAN, CORRUPT, experiment, prepare_pair
from .runtime import MODEL, REVISION, load_model, write_json

SOURCE_LAYER = 6
DOWNSTREAM_LAYER = 8
TOLERANCE = 1e-4
CASES = (
    ("original", CLEAN, CORRUPT, "Mary", "John"),
    ("reverse", CORRUPT, CLEAN, "John", "Mary"),
    (
        "names",
        "When Alice and Bob went to the shops, Alice gave the bag to",
        "When Alice and Bob went to the shops, Bob gave the bag to",
        "Bob",
        "Alice",
    ),
    (
        "template",
        "After Sarah and David went to the park, David gave a book to",
        "After Sarah and David went to the park, Sarah gave a book to",
        "Sarah",
        "David",
    ),
)


def evaluate_case(model, tokenizer, case):
    import torch

    case_id, clean, corrupt, target, contrast = case
    clean_ids, corrupt_ids, target_id, contrast_id, changed = prepare_pair(
        tokenizer, clean, corrupt, target, contrast
    )
    last = clean_ids.shape[1] - 1
    if len(changed) != 1 or changed[0] >= last - 1:
        raise ValueError(f"{case_id}: the edit must affect one token before the final two")
    edited = changed[0]
    blocks = model.transformer.h

    def score(tokens):
        logits = model(tokens, use_cache=False).logits[0, -1]
        return (logits[target_id] - logits[contrast_id]).item()

    with torch.inference_mode():
        with capture(blocks, [SOURCE_LAYER]) as clean_states:
            clean_score = score(clean_ids)
        with capture(blocks, [SOURCE_LAYER, DOWNSTREAM_LAYER]) as corrupt_states:
            corrupt_score = score(corrupt_ids)
        restored_state = clean_states[SOURCE_LAYER][:, edited]
        scores = {"clean": clean_score, "corrupt": corrupt_score}
        with patch(blocks[SOURCE_LAYER], edited, restored_state):
            assert math.isclose(score(clean_ids), clean_score, abs_tol=TOLERANCE), case_id
            scores["restore"] = score(corrupt_ids)
        with patch(blocks[SOURCE_LAYER], edited, corrupt_states[SOURCE_LAYER][:, edited]):
            assert math.isclose(score(corrupt_ids), corrupt_score, abs_tol=TOLERANCE), case_id
        for label, position in (("last", last), ("adjacent", last - 1)):
            fixed_state = corrupt_states[DOWNSTREAM_LAYER][:, position]
            with patch(blocks[DOWNSTREAM_LAYER], position, fixed_state):
                scores[f"clamp_{label}"] = score(corrupt_ids)
                with patch(blocks[SOURCE_LAYER], edited, restored_state):
                    scores[f"restore_clamp_{label}"] = score(corrupt_ids)
            assert math.isclose(scores[f"clamp_{label}"], corrupt_score, abs_tol=TOLERANCE), case_id

    assert all(math.isfinite(value) for value in scores.values()), case_id
    assert clean_score > 0 > corrupt_score, f"{case_id}: the baseline preference did not reverse"
    return {
        "id": case_id,
        "clean_prompt": clean,
        "corrupt_prompt": corrupt,
        "target": target,
        "contrast": contrast,
        "edited_position": edited,
        "last_position": last,
        "scores": scores,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("site/ioi.json"))
    args = parser.parse_args()
    try:
        model, tokenizer = load_model()
    except RuntimeError as error:
        parser.exit(2, f"{error}\n")

    scan = experiment(model, tokenizer)
    cases = [evaluate_case(model, tokenizer, case) for case in CASES]
    original = cases[0]
    assert len(scan["patches"]) == 24
    assert all(
        math.isclose(scan[f"{condition}_score"], original["scores"][condition], abs_tol=TOLERANCE)
        for condition in ("clean", "corrupt")
    )
    original_patch = next(
        row for row in scan["patches"]
        if (row["layer"], row["position"]) == (SOURCE_LAYER, original["edited_position"])
    )
    assert math.isclose(original_patch["patched_score"], original["scores"]["restore"], abs_tol=TOLERANCE)
    write_json(args.output, {
        "model": MODEL,
        "revision": REVISION,
        "source_layer": SOURCE_LAYER,
        "downstream_layer": DOWNSTREAM_LAYER,
        "scan": {key: scan[key] for key in ("tokens", "patches", "clean_score", "corrupt_score", "controls")},
        "cases": cases,
    })
    print(f"Saved IOI study measurements to {args.output}")


if __name__ == "__main__":
    main()
