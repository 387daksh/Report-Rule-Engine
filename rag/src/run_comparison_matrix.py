"""
run_comparison_matrix.py
--------------------------
D2/D3/D5 multi-axis ablation matrix driver.

Supported Matrix Axes:
  --matrix llm        Compare candidate LLMs (qwen3:8b vs qwen3:14b vs llama3.1:8b vs mistral:7b)
  --matrix icl        Compare zero-shot vs fixed_few_shot vs retrieval_few_shot
  --matrix chunking   Compare fixed vs structure_aware vs semantic vs contextual vs docling_hybrid
  --matrix retrieval  Compare dense vs hybrid vs reranked
  --matrix crag       Compare crag_enabled vs crag_disabled
  --matrix prompt     Compare v1_direct vs v2_evidence_review

Outputs:
  - Timestamped runs in results/<run_id>/
  - Single comparison_summary.csv containing Accuracy, Macro-F1, Recall@K, MRR, NDCG@K, Grounding Rate, and Latency
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
from pathlib import Path

from evaluation_harness import run_harness


def _load(path):
    with open(path) as f:
        return json.load(f)


def _write_variant_config(base_cfg: dict, matrix: str, value: str, tmp_path: Path) -> dict:
    cfg = copy.deepcopy(base_cfg)
    if matrix == "llm":
        cfg["generation"]["model_name"] = value
    elif matrix == "icl":
        cfg["icl"]["strategy"] = value
    elif matrix == "chunking":
        if value.startswith("fixed_"):
            _, chunk_tokens, overlap_tokens = value.split("_", 2)
            cfg["chunking"]["strategy"] = "fixed"
            cfg["chunking"]["params"] = {
                "chunk_tokens": int(chunk_tokens),
                "overlap_tokens": int(overlap_tokens),
            }
        else:
            cfg["chunking"]["strategy"] = value
        if value == "fixed":
            params = cfg["chunking"].get("params", {})
            cfg["chunking"]["params"] = {
                "chunk_tokens": params.get("max_tokens", params.get("chunk_tokens", 420)),
                "overlap_tokens": params.get("overlap_tokens", 60),
            }
    elif matrix == "retrieval":
        if value == "dense":
            cfg["retrieval"]["use_hybrid"] = False
            cfg["retrieval"]["use_reranker"] = False
        elif value == "hybrid":
            cfg["retrieval"]["use_hybrid"] = True
            cfg["retrieval"]["use_reranker"] = False
        elif value == "reranked":
            cfg["retrieval"]["use_hybrid"] = True
            cfg["retrieval"]["use_reranker"] = True
    elif matrix == "crag":
        cfg["retrieval"]["use_crag"] = (value.lower() in ("true", "enabled", "yes", "1"))
    elif matrix == "prompt":
        cfg["prompt_version"] = value
    else:
        raise ValueError(f"Unknown matrix: {matrix}")

    with open(tmp_path, "w") as f:
        json.dump(cfg, f, indent=2)
    return cfg


def main():
    parser = argparse.ArgumentParser(description="Run SOTA RAG Ablation Matrix")
    parser.add_argument("--matrix", choices=["llm", "icl", "chunking", "retrieval", "crag", "prompt"], required=True)
    parser.add_argument("--base_config", required=True)
    parser.add_argument("--values", nargs="+", required=True)
    parser.add_argument("--out_dir", default="results")
    parser.add_argument("--summary_csv", default="results/comparison_summary.csv")
    args = parser.parse_args()

    base_cfg = _load(args.base_config)
    summary_rows = []

    for value in args.values:
        tmp_cfg_path = Path(args.out_dir) / f"_tmp_{args.matrix}_{value.replace(':', '_')}.json"
        Path(args.out_dir).mkdir(parents=True, exist_ok=True)
        _write_variant_config(base_cfg, args.matrix, value, tmp_cfg_path)

        print(f"\n=== Running matrix={args.matrix} value={value} ===")
        out_dir = run_harness(str(tmp_cfg_path), args.out_dir)

        row = {"matrix": args.matrix, "value": value, "run_dir": str(out_dir)}

        gen_metrics_path = out_dir / "question_level_llm_metrics.json"
        if gen_metrics_path.exists():
            gm = _load(gen_metrics_path)
            row.update({
                "accuracy": gm.get("accuracy"),
                "macro_f1": gm.get("macro_f1"),
            })

        retr_path = out_dir / "retrieval_metrics.json"
        if args.matrix == "chunking":
            # Gold chunk IDs are defined for the base chunk boundaries.  Reporting
            # their overlap after changing boundaries would be a false comparison.
            row["retrieval_metrics_comparable"] = False
        elif retr_path.exists():
            rm = _load(retr_path)["summary"]
            row.update({
                "mean_precision_at_k": rm.get("mean_precision_at_k"),
                "mean_recall_at_k": rm.get("mean_recall_at_k"),
                "hit_rate_at_k": rm.get("hit_rate_at_k"),
                "mrr": rm.get("mrr"),
                "mean_ndcg_at_k": rm.get("mean_ndcg_at_k"),
            })

        sota_path = out_dir / "sota_faithfulness_metrics.json"
        if sota_path.exists():
            sm = _load(sota_path)
            row.update({
                "evidence_grounding_rate": sm.get("evidence_grounding_rate"),
                "crag_correct_retrieval_rate": sm.get("crag_correct_retrieval_rate"),
            })

        qlr_path = out_dir / "question_level_results.json"
        if qlr_path.exists():
            rows = _load(qlr_path)
            lat = [r["latency_s"] for r in rows if r.get("latency_s") is not None]
            row["mean_latency_s"] = sum(lat) / len(lat) if lat else None

        summary_rows.append(row)

    summary_path = Path(args.summary_csv)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", newline="") as f:
        fieldnames = sorted({k for r in summary_rows for k in r.keys()})
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"\nComparison summary written to {summary_path}")
    for row in summary_rows:
        print(row)


if __name__ == "__main__":
    main()
