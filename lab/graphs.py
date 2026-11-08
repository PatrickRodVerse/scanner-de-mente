"""Export observed activations and measured node interventions using Graphify."""

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys


def activation_extraction(result: dict, source_file: str = "patching.json") -> dict:
    """Preserve experimental evidence without inventing internal causal edges."""
    tokens = result["tokens"]
    norms = result["activation_norms"]
    if not tokens or not norms or any(len(row) != len(tokens) for row in norms):
        raise ValueError("activation_norms must contain one value per layer and token")
    if any(not math.isfinite(float(value)) for row in norms for value in row):
        raise ValueError("activation norms must be finite")

    nodes, edges = [], []

    def node(node_id, label, **attrs):
        nodes.append({"id": node_id, "label": label, "file_type": "concept",
                      "source_file": source_file, **attrs})

    def edge(source, target, relation, evidence_kind, **attrs):
        edges.append({"source": source, "target": target, "relation": relation,
                      "confidence": "EXTRACTED", "source_file": source_file,
                      "evidence_kind": evidence_kind, "weight": 1.0, **attrs})

    for layer, row in enumerate(norms):
        for position, norm in enumerate(row):
            node_id = f"state_L{layer}_T{position}"
            node(node_id, f"L{layer} T{position} {tokens[position]!r} |h|={norm:.3f}",
                 kind="activation", layer=layer, position=position,
                 token=tokens[position], activation_norm=float(norm),
                 source_location=f"activation_norms[{layer}][{position}]")
            if layer:
                edge(f"state_L{layer - 1}_T{position}", node_id,
                     "structural connection between blocks", "architecture")
                for previous in range(position):
                    edge(f"state_L{layer - 1}_T{previous}", node_id,
                         "connection allowed by the causal mask", "architecture")

    node("metric", "Metric: target logit - contrast logit", kind="metric",
         clean_score=result["clean_score"], corrupt_score=result["corrupt_score"],
         source_location="clean_score, corrupt_score")
    seen = set()
    for patch in result["patches"]:
        layer, position = patch["layer"], patch["position"]
        if (not isinstance(layer, int) or not isinstance(position, int)
                or not 0 <= layer < len(norms) or not 0 <= position < len(tokens)):
            raise ValueError("patch layer/position outside activation_norms")
        if (layer, position) in seen:
            raise ValueError("duplicate intervention at one layer/token")
        seen.add((layer, position))
        effect, score, recovery = patch["effect"], patch["patched_score"], patch["recovery"]
        if not all(math.isfinite(float(x)) for x in (effect, score)):
            raise ValueError("patch effects and scores must be finite")
        if recovery is not None and not math.isfinite(float(recovery)):
            raise ValueError("patch recovery must be finite or null")
        patch_id = f"patch_L{layer}_T{position}"
        node(patch_id, f"Patch L{layer} T{position}: effect={effect:+.3f}",
             kind="intervention", layer=layer, position=position,
             patched_score=score, effect_logit_diff=effect, recovery=recovery,
             source_location=f"patches[layer={layer},position={position}]")
        edge(f"state_L{layer}_T{position}", patch_id,
             "site of the reference-state substitution", "intervention_site")
        edge(patch_id, "metric", f"measured effect on the metric: {effect:+.3f}",
             "node_intervention", effect_logit_diff=effect,
             patched_score=score, recovery=recovery)

    return {"nodes": nodes, "edges": edges, "hyperedges": [],
            "input_tokens": 0, "output_tokens": 0}


def _write_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False),
                    encoding="utf-8")


def _export_worker(args):
    from graphify.analyze import god_nodes, surprising_connections, suggest_questions
    from graphify.build import build_from_json
    from graphify.cluster import cluster, score_all
    from graphify.detect import detect, save_manifest
    from graphify.diagnostics import diagnose_extraction, format_diagnostic_report
    from graphify.export import to_html, to_json
    from graphify.extract import extract
    from graphify.report import generate

    output = args.output.resolve()
    root = Path(__file__).resolve().parents[1]
    scan_root = root / "lab" if args.repo else root
    output.mkdir(parents=True, exist_ok=True)
    if args.repo:
        # Scan only the owned source directory, never the model cache or environment.
        detection = detect(scan_root)
        files = [Path(p) for p in detection["files"].get("code", [])]
        if detection["total_files"] > 500 or detection["total_words"] > 2_000_000:
            raise ValueError("source corpus exceeds the small-lab scan limit")
        if detection.get("skipped_sensitive"):
            print("Skipped sensitive files: " + ", ".join(detection["skipped_sensitive"]))
        print(f"Corpus: {len(files)} source files, ~{detection['total_words']} words")
        if detection.get("warning"):
            print(detection["warning"])
        if not files:
            raise ValueError("No supported source files found in lab/")
        extraction = extract(files, cache_root=root, root=scan_root, parallel=False)
        extraction.update(input_tokens=0, output_tokens=0)
        _write_json(output / ".graphify_detect.json", detection)
        _write_json(output / ".graphify_ast.json", extraction)
        _write_json(output / ".graphify_semantic.json", {
            "nodes": [], "edges": [], "hyperedges": [],
            "input_tokens": 0, "output_tokens": 0})
        meaning = ("Source-only AST graph of lab/. Imports and calls describe repository "
                   "structure, not neural circuits. No semantic LLM extraction was used.")
    else:
        result_path = args.results.resolve()
        result = json.loads(result_path.read_text(encoding="utf-8"))
        extraction = activation_extraction(result, str(result_path))
        detection = {"total_files": 1, "total_words": 0,
                     "warning": "Experimental graph from numeric observations; no corpus-size claim."}
        meaning = (
            "Norms describe observed activation magnitudes. Structural links show connections "
            "allowed by the causal mask. Intervention → metric links show measured causal "
            "effects for this prompt pair and metric. Circuit attribution and SAE feature "
            "interpretation require additional evidence. EXTRACTED labels deterministic provenance."
        )

    _write_json(output / "extraction.json", extraction)
    graph = build_from_json(extraction, root=scan_root, directed=True)
    if not graph.number_of_nodes():
        raise ValueError("Graphify extraction produced no nodes; existing outputs preserved")
    if graph.number_of_nodes() > 5000:
        raise ValueError("Graph exceeds 5000 nodes; reduce tokens/layers before HTML export")
    communities = cluster(graph)
    cohesion = score_all(graph, communities)
    labels = {}
    for cid, members in communities.items():
        if args.repo:
            hub = max(members, key=lambda n: graph.degree(n))
            name = Path(graph.nodes[hub].get("source_file") or "").stem
            if not name:
                name = next((Path(graph.nodes[n]["source_file"]).stem for n in members
                             if graph.nodes[n].get("source_file")), "lab")
            labels[cid] = "Code " + name
        else:
            labels[cid] = ("Interventions and metric" if any(
                graph.nodes[n].get("kind") in ("metric", "intervention") for n in members
            ) else "Observed activations")
    questions = suggest_questions(graph, communities, labels)
    if not to_json(graph, communities, str(output / "graph.json"), community_labels=labels):
        raise ValueError("Graphify refused to replace a larger graph; choose a new output directory")
    report = generate(graph, communities, cohesion, labels, god_nodes(graph),
                      surprising_connections(graph, communities), detection,
                      {"input": 0, "output": 0}, str(scan_root), suggested_questions=questions)
    diagnostics = diagnose_extraction(extraction, directed=True, root=scan_root)
    diagnostic_report = format_diagnostic_report(diagnostics)
    report += ("\n\n## Evidence and limits\n\n" + meaning
               + "\n\nGraphify processes the graph locally. Its HTML viewer loads vis-network "
               "from the unpkg CDN unless it is already cached.\n\n"
               + "## Graph health\n\n```text\n" + diagnostic_report + "\n```\n")
    (output / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
    _write_json(output / "diagnostics.json", diagnostics)
    _write_json(output / ".graphify_labels.json", {str(k): v for k, v in labels.items()})
    _write_json(output / ".graphify_analysis.json", {
        "communities": communities, "cohesion": cohesion, "questions": questions})
    if not to_html(graph, communities, str(output / "graph.html"), community_labels=labels):
        raise ValueError("Graphify did not write the HTML graph")
    if args.repo:
        file_map = {"code": [str(p) for p in files]}
        save_manifest(file_map, str(output / "manifest.json"), kind="ast", root=scan_root,
                      scan_corpus=set(file_map["code"]))
        (output / ".graphify_root").write_text(str(scan_root), encoding="utf-8")
    (output / ".graphify_python").write_text(sys.executable, encoding="utf-8")
    _write_json(output / "cost.json", {"input_tokens": 0, "output_tokens": 0,
                                      "method": "deterministic; no LLM calls"})
    print(diagnostic_report)
    print(f"Graphify: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges; {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--results", type=Path)
    source.add_argument("--repo", action="store_true", help="Graph only lab/ Python source")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--graphify-python", type=Path, default=Path(sys.executable))
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.output = args.output or Path("graphify-out" if args.repo else "artifacts/circuit")
    if args.worker:
        _export_worker(args)
        return
    command = [str(args.graphify_python), "-X", "utf8", str(Path(__file__).resolve()),
               "--worker", "--output", str(args.output.resolve())]
    command += ["--repo"] if args.repo else ["--results", str(args.results.resolve())]
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
