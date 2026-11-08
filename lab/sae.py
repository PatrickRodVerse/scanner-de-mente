"""Educational, single-layer SAE trained on a bounded CPU activation cache.

Sparse dictionary directions are candidate features, not proven concepts or a
measurement of superposition. Inspect held-out activating contexts and perform
causal interventions before assigning a semantic label. Tiny caches can only
validate the training pipeline. Normalization is fitted on the training split.
"""

import argparse
import json
from pathlib import Path
import warnings

import torch
from torch import nn
from torch.nn import functional as F


class SparseAutoencoder(nn.Module):
    def __init__(self, input_dim, features, center=None, scale=None):
        super().__init__()
        if not 1 <= input_dim <= 4096 or not 1 <= features <= 8192:
            raise ValueError("input_dim must be 1..4096 and features 1..8192")
        self.register_buffer("center", torch.zeros(input_dim) if center is None else center.clone())
        self.register_buffer("scale", torch.tensor(1.0) if scale is None else scale.clone())
        if self.center.shape != (input_dim,) or self.scale.numel() != 1:
            raise ValueError("Invalid normalization shape")
        if not torch.isfinite(self.center).all() or not torch.isfinite(self.scale).all() or self.scale <= 0:
            raise ValueError("Normalization must be finite with positive scale")
        self.encoder = nn.Linear(input_dim, features)
        self.decoder = nn.Linear(features, input_dim, bias=False)
        self.normalize_decoder()

    @torch.no_grad()
    def normalize_decoder(self):
        self.decoder.weight.copy_(F.normalize(self.decoder.weight, dim=0))

    def forward(self, activations):
        normalized = (activations - self.center) / self.scale
        features = F.relu(self.encoder(normalized))
        reconstruction = self.decoder(features) * self.scale + self.center
        return reconstruction, features


def validate_cache(activations, contexts):
    if not isinstance(activations, torch.Tensor) or activations.ndim != 2:
        raise ValueError("activations must be a tensor [N, d]")
    rows, width = activations.shape
    if not 2 <= rows <= 32768 or not 1 <= width <= 4096:
        raise ValueError("Cache requires 2..32768 rows and 1..4096 dimensions")
    if not activations.is_floating_point() or not torch.isfinite(activations).all():
        raise ValueError("Activations must be finite floating-point values")
    if not isinstance(contexts, list) or len(contexts) != rows or not all(isinstance(x, str) for x in contexts):
        raise ValueError("contexts must contain one string per activation row")


def split_contexts(contexts, generator):
    groups = {}
    for index, context in enumerate(contexts):
        groups.setdefault(context, []).append(index)
    if len(groups) < 3:
        warnings.warn("Cache has at most two distinct contexts; this is a pipeline demonstration, not semantic evidence.", stacklevel=2)
    if len(groups) == 1:
        warnings.warn("Only one context: token-row holdout is not an independent-context evaluation.", stacklevel=2)
        order = torch.randperm(len(contexts), generator=generator)
        count = max(1, len(contexts) // 5)
        return order[count:], order[:count], "token_rows_one_context"
    keys = list(groups)
    order = torch.randperm(len(keys), generator=generator).tolist()
    holdout_groups = set(order[:max(1, len(keys) // 5)])
    train = [i for group, key in enumerate(keys) if group not in holdout_groups for i in groups[key]]
    holdout = [i for group, key in enumerate(keys) if group in holdout_groups for i in groups[key]]
    return torch.tensor(train), torch.tensor(holdout), "distinct_context_groups"


@torch.no_grad()
def evaluate(model, activations, indices, batch_size):
    squared_error = baseline = nonzero = 0.0
    active = torch.zeros(model.encoder.out_features, dtype=torch.bool)
    for batch in indices.split(batch_size):
        values = activations[batch]
        reconstruction, features = model(values)
        squared_error += (((reconstruction - values) / model.scale).square()).sum().item()
        baseline += (((values - model.center) / model.scale).square()).sum().item()
        nonzero += (features > 0).sum().item()
        active |= (features > 0).any(dim=0)
    count = len(indices) * activations.shape[1]
    return {
        "reconstruction_mse": squared_error / count,
        "baseline_mse": baseline / count,
        "normalized_mse": squared_error / baseline if baseline > 1e-12 else None,
        "mean_l0": nonzero / len(indices),
        "dead_fraction": (~active).float().mean().item(),
    }


@torch.no_grad()
def top_contexts(model, activations, contexts, indices, batch_size):
    # shortcut: report at most 32 features, expand after validating on a representative corpus.
    maxima = torch.zeros(model.encoder.out_features)
    winners = torch.full((model.encoder.out_features,), -1, dtype=torch.long)
    for batch in indices.split(batch_size):
        _, features = model(activations[batch])
        values, positions = features.max(dim=0)
        improved = values > maxima
        maxima[improved] = values[improved]
        winners[improved] = batch[positions[improved]]
    selected = torch.argsort(maxima, descending=True)[:32]
    return [
        {"feature": feature, "activation": maxima[feature].item(),
         "row": winners[feature].item(), "context": contexts[winners[feature].item()],
         "semantic_label": None}
        for feature in selected.tolist() if winners[feature] >= 0
    ]


def train_sae(activations, contexts, *, features=1536, steps=200, batch_size=64, seed=0, groups=None):
    validate_cache(activations, contexts)
    if not 1 <= features <= 8192 or not 1 <= steps <= 10000 or not 1 <= batch_size <= 1024:
        raise ValueError("features must be 1..8192, steps 1..10000, batch_size 1..1024")
    if len(contexts) < 1024:
        warnings.warn("Fewer than 1024 activation rows: SAE quality and feature labels cannot be established.", stacklevel=2)
    torch.set_num_threads(4)
    torch.manual_seed(seed)
    generator = torch.Generator().manual_seed(seed)
    activations = activations.detach().to(device="cpu", dtype=torch.float32)
    if groups is not None and (len(groups) != len(contexts) or not all(isinstance(x, str) for x in groups)):
        raise ValueError("groups must contain the source sentence for each activation row")
    train, holdout, split_kind = split_contexts(contexts if groups is None else groups, generator)
    center = activations[train].mean(dim=0)
    scale = (activations[train] - center).square().mean().sqrt()
    if not torch.isfinite(scale) or scale <= 1e-8:
        raise ValueError("Training activations need nonzero finite RMS variation")
    model = SparseAutoencoder(activations.shape[1], features, center, scale)
    initial = evaluate(model, activations, train, batch_size)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    model.train()
    for _ in range(steps):
        batch = train[torch.randint(len(train), (min(batch_size, len(train)),), generator=generator)]
        values = activations[batch]
        reconstruction, encoded = model(values)
        mse = ((reconstruction - values) / scale).square().mean()
        loss = mse + 1e-3 * encoded.sum(dim=-1).mean()
        if not torch.isfinite(loss):
            raise RuntimeError("SAE loss became non-finite")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        model.normalize_decoder()
    model.eval()
    metrics = {
        "seed": seed, "steps": steps, "features": features, "l1_coefficient": 1e-3,
        "train_rows": len(train), "holdout_rows": len(holdout), "split": split_kind,
        "grouped_by_source_sentence": groups is not None,
        "train_initial": initial,
        "train_final": evaluate(model, activations, train, batch_size),
        "holdout": evaluate(model, activations, holdout, batch_size),
        "interpretation": "Candidate dictionary features; no automatic semantic labels or proof of superposition.",
    }
    return model, metrics, top_contexts(model, activations, contexts, holdout, batch_size)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("artifacts/sae"))
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--features", type=int, default=1536)
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()
    import psutil

    if psutil.virtual_memory().available < 1024 ** 3:
        parser.error("SAE training requires at least 1 GiB of available RAM")
    if not args.cache.is_file() or args.cache.stat().st_size > 600 * 1024 ** 2:
        parser.error("Cache file exceeds the 600 MiB safety limit")
    cache = torch.load(args.cache, map_location="cpu", weights_only=True)
    if not isinstance(cache, dict) or not {"activations", "contexts", "model", "layer"} <= cache.keys():
        parser.error("Cache needs activations, contexts, model and layer")
    validate_cache(cache["activations"], cache["contexts"])
    if not isinstance(cache["model"], str) or not isinstance(cache["layer"], int) or cache["layer"] < 0:
        parser.error("Invalid cache model/layer metadata")
    width = cache["activations"].shape[1]
    estimated = 32 * width * args.features + 16 * args.batch_size * (width + args.features) + 256 * 1024 ** 2
    if psutil.virtual_memory().available < max(1024 ** 3, estimated):
        parser.error("Insufficient available RAM for the requested SAE dimensions")
    model, metrics, top = train_sae(cache["activations"], cache["contexts"], features=args.features,
                                    steps=args.steps, batch_size=args.batch_size, groups=cache.get("groups"))
    metrics.update(model=cache["model"], layer=cache["layer"])
    args.output.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "input_dim": width, "features": args.features,
                "model": cache["model"], "layer": cache["layer"]}, args.output / "sae.pt")
    (args.output / "metrics.json").write_text(json.dumps(metrics, indent=2, allow_nan=False), encoding="utf-8")
    (args.output / "top_features.json").write_text(json.dumps(top, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(json.dumps(metrics, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
