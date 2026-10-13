"""
evaluation_harness.py
----------------------
SOTA Automated Evaluation Harness for AI-Based Cybersecurity Audit Assessment.

Metric Families Produced:
  1. Question-level results  - (report, question): retrieved chunks, scores,
     verdict, supporting evidence, CRAG decisions, latency, configuration.
  2. Retrieval metrics        - Precision@K, Recall@K, Hit Rate@K, MRR, and NDCG@K.
  3. Question-level LLM       - Accuracy, Precision, Recall, F1, Macro-F1, Confusion Matrix.
  4. SOTA Faithfulness/CRAG   - Grounding rate, citation consistency, CRAG ambiguity rates.
  5. Audit-level metrics      - Compliance threshold scoring, Pass/Fail decision.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import time
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from chunking import STRATEGIES as CHUNK_STRATEGIES, Chunk
from docling_parser import parse_document
from embed_index import (
    CrossEncoderReranker,
    Embedder,
    HybridRetrievalIndex,
    RetrievalIndex,
    build_hybrid_index,
    build_index,
)
from icl import STRATEGIES as ICL_STRATEGIES, load_example_bank
from llm_client import GenerationConfig
from pii_redaction import redact_if_enabled
from pipeline import AuditAssessmentPipeline, PipelineConfig
from advanced_retrieval import GraphEvidenceIndex, LateInteractionIndex, ParentChildRetriever, require_local_path

ANSWER_CLASSES = ["Yes", "No", "Insufficient Evidence"]

logger = logging.getLogger("audit_rag.harness")


def _setup_logging(out_dir: Path) -> None:
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    file_handler = logging.FileHandler(out_dir / "run.log")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)


REQUIRED_CONFIG_KEYS = [
    "chunking", "retrieval", "icl", "prompt_version", "generation",
    "benchmark_questions_path", "audit_reports",
]


def validate_config(cfg: dict) -> List[str]:
    problems = []
    for key in REQUIRED_CONFIG_KEYS:
        if key not in cfg:
            problems.append(f"missing required config key: '{key}'")
    if problems:
        return problems

    if cfg["chunking"].get("strategy") not in CHUNK_STRATEGIES:
        problems.append(f"chunking.strategy must be one of {list(CHUNK_STRATEGIES)}")
    if cfg["icl"].get("strategy") not in ICL_STRATEGIES:
        problems.append(f"icl.strategy must be one of {list(ICL_STRATEGIES)}")
    if not Path(cfg["benchmark_questions_path"]).exists():
        problems.append(f"benchmark_questions_path not found: {cfg['benchmark_questions_path']}")
    if not cfg["audit_reports"]:
        problems.append("audit_reports must contain at least one report")
    for report in cfg.get("audit_reports", []):
        for k in ("report_id", "path"):
            if k not in report:
                problems.append(f"audit_reports entry missing '{k}': {report}")
        if "path" in report and not Path(report["path"]).exists():
            problems.append(f"audit report file not found: {report['path']}")
    icl_cfg = cfg["icl"]
    if icl_cfg["strategy"] != "zero_shot" and not icl_cfg.get("example_bank_path"):
        problems.append("icl.example_bank_path is required for non-zero_shot ICL strategies")
    if icl_cfg.get("example_bank_path") and not Path(icl_cfg["example_bank_path"]).exists():
        problems.append(f"icl.example_bank_path not found: {icl_cfg['example_bank_path']}")
    return problems


# --------------------------------------------------------------------------
# Retrieval metrics (Precision, Recall, Hit Rate, MRR, NDCG@K)
# --------------------------------------------------------------------------

def retrieval_metrics_for_query(retrieved_ids: List[str], gold_ids: List[str], k: int) -> dict:
    retrieved_k = retrieved_ids[:k]
    gold_set = set(gold_ids)
    hits = [1 if rid in gold_set else 0 for rid in retrieved_k]
    n_relevant_retrieved = sum(hits)

    precision_at_k = n_relevant_retrieved / max(1, len(retrieved_k))
    recall_at_k = n_relevant_retrieved / max(1, len(gold_set)) if gold_set else np.nan
    hit_rate_at_k = 1.0 if n_relevant_retrieved > 0 else 0.0

    rr = 0.0
    for rank, rid in enumerate(retrieved_k, start=1):
        if rid in gold_set:
            rr = 1.0 / rank
            break

    # NDCG@K
    dcg = 0.0
    for rank, rid in enumerate(retrieved_k, start=1):
        if rid in gold_set:
            dcg += 1.0 / np.log2(rank + 1)
    idcg = sum(1.0 / np.log2(i + 1) for i in range(1, min(len(gold_set), k) + 1))
    ndcg = float(dcg / idcg) if idcg > 0 else 0.0

    return {
        "precision_at_k": precision_at_k,
        "recall_at_k": recall_at_k,
        "hit_rate_at_k": hit_rate_at_k,
        "reciprocal_rank": rr,
        "ndcg_at_k": ndcg,
    }


def aggregate_retrieval_metrics(per_query: List[dict]) -> dict:
    def _mean(key):
        vals = [r[key] for r in per_query if not np.isnan(r[key])]
        return float(np.mean(vals)) if vals else None

    return {
        "mean_precision_at_k": _mean("precision_at_k"),
        "mean_recall_at_k": _mean("recall_at_k"),
        "hit_rate_at_k": _mean("hit_rate_at_k"),
        "mrr": _mean("reciprocal_rank"),
        "mean_ndcg_at_k": _mean("ndcg_at_k"),
        "n_queries": len(per_query),
    }


# --------------------------------------------------------------------------
# Question-level LLM classification metrics
# --------------------------------------------------------------------------

def confusion_matrix(y_true: List[str], y_pred: List[str], classes: List[str]) -> np.ndarray:
    idx = {c: i for i, c in enumerate(classes)}
    cm = np.zeros((len(classes), len(classes)), dtype=int)
    for t, p in zip(y_true, y_pred):
        ti = idx.get(t)
        pi = idx.get(p, idx.get("Insufficient Evidence"))
        if ti is None:
            continue
        cm[ti, pi if pi is not None else ti] += 1
    return cm


def classification_metrics(y_true: List[str], y_pred: List[str], classes: List[str] = ANSWER_CLASSES) -> dict:
    cm = confusion_matrix(y_true, y_pred, classes)
    n = cm.sum()
    accuracy = float(np.trace(cm) / n) if n else None

    per_class = {}
    f1s = []
    for i, c in enumerate(classes):
        tp = cm[i, i]
        fp = cm[:, i].sum() - tp
        fn = cm[i, :].sum() - tp
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        per_class[c] = {"precision": precision, "recall": recall, "f1": f1, "support": int(cm[i, :].sum())}
        f1s.append(f1)

    macro_f1 = float(np.mean(f1s)) if f1s else None

    return {
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "per_class": per_class,
        "confusion_matrix": cm.tolist(),
        "classes": classes,
    }


# --------------------------------------------------------------------------
# Audit-level scoring
# --------------------------------------------------------------------------

def audit_level_score(question_results: List[dict], pass_threshold_pct: float = 70.0) -> dict:
    n_total = len(question_results)
    n_positive = sum(1 for r in question_results if r["answer"] == "Yes")
    n_negative = sum(1 for r in question_results if r["answer"] == "No")
    n_insufficient = sum(1 for r in question_results if r["answer"] == "Insufficient Evidence")
    pct_satisfied = (n_positive / n_total * 100) if n_total else 0.0

    return {
        "n_questions": n_total,
        "n_positive": n_positive,
        "n_negative": n_negative,
        "n_insufficient_evidence": n_insufficient,
        "total_benchmark_score": n_positive,
        "percentage_requirements_satisfied": round(pct_satisfied, 2),
        "benchmark_decision": "PASS" if pct_satisfied >= pass_threshold_pct else "FAIL",
        "pass_threshold_pct": pass_threshold_pct,
    }


def production_readiness_gate(cfg: dict, question_rows: List[dict], retrieval_summary: dict | None,
                              sota_metrics: dict, gen_metrics: dict | None) -> dict:
    """Conservative release gate; small/source-derived benchmarks cannot pass it."""
    labelled = [r for r in question_rows if r.get("gold_answer")]
    classes = {r["gold_answer"] for r in labelled}
    gate_cfg = cfg.get("production_gate", {})
    checks = {
        "minimum_reports": len(cfg.get("audit_reports", [])) >= gate_cfg.get("minimum_reports", 5),
        "minimum_labelled_questions": len(labelled) >= gate_cfg.get("minimum_labelled_questions", 100),
        "balanced_answer_classes": set(ANSWER_CLASSES).issubset(classes),
        "retrieval_recall": bool(retrieval_summary) and retrieval_summary.get("mean_recall_at_k", 0) >= gate_cfg.get("minimum_recall", 0.90),
        "grounding": sota_metrics.get("evidence_grounding_rate", 0) >= gate_cfg.get("minimum_grounding", 0.99),
        "macro_f1": bool(gen_metrics) and gen_metrics.get("macro_f1", 0) >= gate_cfg.get("minimum_macro_f1", 0.70),
    }
    return {
        "status": "PASS" if all(checks.values()) else "BLOCKED",
        "checks": checks,
        "observed": {"reports": len(cfg.get("audit_reports", [])), "labelled_questions": len(labelled), "gold_classes": sorted(classes)},
        "reason": "All release checks passed." if all(checks.values()) else "Insufficient evidence for production release; collect independent balanced labels and rerun.",
    }


# --------------------------------------------------------------------------
# Harness orchestration
# --------------------------------------------------------------------------

def _hash_config(cfg: dict) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:12]


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve_path(path_str: Optional[str], base_dir: Path) -> Optional[str]:
    if not path_str:
        return path_str
    p = Path(path_str)
    if p.is_absolute() and p.exists():
        return str(p)
    if p.exists():
        return str(p.resolve())

    script_dir = Path(__file__).resolve().parent
    rag_root = script_dir.parent

    candidates = [
        (base_dir / p),
        (base_dir.parent / p),
        (script_dir / p),
        (rag_root / p),
        (rag_root / "sample_data" / p.name),
        (Path.cwd() / p),
        (Path.cwd().parent / p),
    ]
    for cand in candidates:
        if cand.exists():
            return str(cand.resolve())
    return str(p)


def run_harness(config_path: str, out_dir: str = "results"):
    config_file = Path(config_path).resolve()
    base_dir = config_file.parent

    with open(config_path) as f:
        cfg = json.load(f)

    # Normalize relative paths in cfg
    if "benchmark_questions_path" in cfg:
        cfg["benchmark_questions_path"] = _resolve_path(cfg["benchmark_questions_path"], base_dir)
    if "icl" in cfg and "example_bank_path" in cfg["icl"]:
        cfg["icl"]["example_bank_path"] = _resolve_path(cfg["icl"]["example_bank_path"], base_dir)
    for section, keys in (("retrieval", ("embed_model", "reranker_model", "late_interaction_model_path", "visual_model_path")), ("generation", ("model_path",))):
        for key in keys:
            if cfg.get(section, {}).get(key):
                cfg[section][key] = _resolve_path(cfg[section][key], base_dir)
    for report in cfg.get("audit_reports", []):
        if "path" in report:
            report["path"] = _resolve_path(report["path"], base_dir)

    run_id = f"{int(time.time())}_{_hash_config(cfg)}"
    out = Path(out_dir) / run_id
    out.mkdir(parents=True, exist_ok=True)
    _setup_logging(out)

    problems = validate_config(cfg)
    if problems:
        for p in problems:
            logger.error("config problem: %s", p)
        raise ValueError(
            f"{len(problems)} problem(s) found in {config_path} — fix these before running."
        )

    logger.info("run_id=%s writing to %s", run_id, out)

    # --- 1. Load reports, chunk, embed, index -----------------------------
    embed_model_name = cfg.get("retrieval", {}).get("embed_model", "BAAI/bge-m3")
    embedder = Embedder(
        model_name=embed_model_name,
        device=cfg.get("retrieval", {}).get("embed_device", cfg.get("device", "cpu")),
        query_instruction=cfg.get("retrieval", {}).get("query_instruction", ""),
    )
    chunker_cls = CHUNK_STRATEGIES[cfg["chunking"]["strategy"]]
    if cfg["chunking"]["strategy"] == "semantic":
        chunker = chunker_cls(embed_fn=embedder, **cfg["chunking"].get("params", {}))
    else:
        chunker = chunker_cls(**cfg["chunking"].get("params", {}))

    redact_pii = cfg.get("redact_pii", False)
    all_chunks: List[Chunk] = []

    for report in cfg["audit_reports"]:
        parsed = parse_document(report["path"], report_id=report["report_id"])
        text = redact_if_enabled(parsed.full_text, redact_pii)
        report_chunks = chunker.chunk(report["report_id"], text)
        if not report_chunks:
            logger.warning("report %s produced ZERO chunks.", report["report_id"])
        all_chunks.extend(report_chunks)

    logger.info(
        "chunked %d report(s) into %d chunks (strategy=%s, embedder=%s)",
        len(cfg["audit_reports"]), len(all_chunks), cfg["chunking"]["strategy"], embedder.model_name
    )

    use_hybrid = cfg.get("retrieval", {}).get("use_hybrid", True)
    use_reranker = cfg.get("retrieval", {}).get("use_reranker", True)

    reranker = None
    if use_reranker:
        reranker_model = cfg.get("retrieval", {}).get("reranker_model", "BAAI/bge-reranker-v2-m3")
        reranker = CrossEncoderReranker(
            model_name=reranker_model,
            device=cfg.get("retrieval", {}).get("reranker_device", cfg.get("device", "cpu")),
        )

    if use_hybrid:
        index = build_hybrid_index(all_chunks, embedder, reranker=reranker)
        index.save(str(out / "index"))
    else:
        index = build_index(all_chunks, embedder)
        index.save(str(out / "index"))

    # --- 2. Build ICL selector --------------------------------------------
    icl_cfg = cfg["icl"]
    example_bank = load_example_bank(icl_cfg["example_bank_path"]) if icl_cfg.get("example_bank_path") else []
    icl_cls = ICL_STRATEGIES[icl_cfg["strategy"]]
    if icl_cfg["strategy"] == "retrieval_few_shot":
        icl_selector = icl_cls(example_bank, embedder, k=icl_cfg.get("k", 4))
    elif icl_cfg["strategy"] == "fixed_few_shot":
        icl_selector = icl_cls(example_bank, k=icl_cfg.get("k", 3))
    else:
        icl_selector = icl_cls()

    # --- 3. Build pipeline ---------------------------------------------------
    pipeline_cfg = PipelineConfig(
        top_k=cfg["retrieval"]["top_k"],
        candidates_k=cfg.get("retrieval", {}).get("candidates_k", 40),
        prompt_version=cfg["prompt_version"],
        icl_strategy_name=icl_cfg["strategy"],
        icl_k=icl_cfg.get("k", 4),
        use_hybrid=use_hybrid,
        use_reranker=use_reranker,
        use_crag=cfg.get("retrieval", {}).get("use_crag", True),
        use_hyde=cfg.get("retrieval", {}).get("use_hyde", False),
        generation=GenerationConfig(**cfg["generation"]),
        min_retrieval_score=cfg.get("retrieval", {}).get("min_retrieval_score", 0.02),
        require_evidence_for_yes_no=cfg.get("verification", {}).get("require_evidence_for_yes_no", True),
        use_parent_child=cfg.get("retrieval", {}).get("use_parent_child", False),
        use_graph_retrieval=cfg.get("retrieval", {}).get("use_graph_retrieval", False),
        parent_child=ParentChildRetriever(all_chunks) if cfg.get("retrieval", {}).get("use_parent_child", False) else None,
        graph_index=GraphEvidenceIndex(all_chunks) if cfg.get("retrieval", {}).get("use_graph_retrieval", False) else None,
        late_interaction=(lambda idx: (idx.add(all_chunks), idx)[1])(
            LateInteractionIndex(require_local_path(cfg["retrieval"]["late_interaction_model_path"]), device=cfg.get("device", "cpu"))
        ) if cfg.get("retrieval", {}).get("use_late_interaction", False) else None,
        use_claim_verifier=cfg.get("verification", {}).get("use_claim_verifier", False),
        fail_closed_on_unsupported=cfg.get("verification", {}).get("fail_closed_on_unsupported", True),
        redact_persisted_output=cfg.get("redact_persisted_output", True),
    )
    pipeline = AuditAssessmentPipeline(index, embedder, icl_selector, pipeline_cfg)

    # --- 4. Load benchmark question set + gold labels ----------------------
    with open(cfg["benchmark_questions_path"]) as f:
        questions = json.load(f)

    # --- 5. Run pipeline over every (report, question) pair -----------------
    question_rows = []
    retrieval_rows = []
    human_review_queue = []
    per_report_answers: Dict[str, List[dict]] = defaultdict(list)
    n_errors = 0

    for report in cfg["audit_reports"]:
        rid = report["report_id"]
        gold_map = report.get("gold_labels", {})
        for q in questions:
            try:
                result = pipeline.assess(rid, q["question_id"], q["text"])
            except Exception as e:
                n_errors += 1
                logger.error("assess() failed for %s / %s: %s", rid, q["question_id"], e)
                row = {
                    "report_id": rid, "question_id": q["question_id"], "question_text": q["text"],
                    "retrieved_chunk_ids": [], "retrieved_scores": [], "raw_llm_output": "",
                    "answer": "Error", "supporting_evidence": "", "cited_chunk_ids": [],
                    "justification": f"Pipeline error: {e}", "latency_s": None, "config": {},
                    "crag_verdict": "ERROR", "crag_reformulated": False, "is_evidence_grounded": False,
                    "requires_human_review": True, "review_reasons": ["pipeline_exception"],
                    "gold_answer": gold_map.get(q["question_id"], {}).get("answer"),
                    "gold_chunk_ids": gold_map.get(q["question_id"], {}).get("gold_chunk_ids", []),
                }
                question_rows.append(row)
                per_report_answers[rid].append({"answer": "Error"})
                human_review_queue.append(row)
                continue

            row = asdict(result)
            gold = gold_map.get(q["question_id"], {})
            row["gold_answer"] = gold.get("answer")
            row["gold_chunk_ids"] = gold.get("gold_chunk_ids", [])
            question_rows.append(row)
            per_report_answers[rid].append({"answer": result.answer})

            if result.requires_human_review:
                human_review_queue.append(row)

            if row["gold_chunk_ids"]:
                rmet = retrieval_metrics_for_query(
                    result.retrieved_chunk_ids, row["gold_chunk_ids"], k=pipeline_cfg.top_k
                )
                rmet.update({"report_id": rid, "question_id": q["question_id"]})
                retrieval_rows.append(rmet)

            flag = " [REVIEW: " + ",".join(result.review_reasons) + "]" if result.requires_human_review else ""
            logger.info(
                "[%s / %s] -> %s (%.1fs, CRAG: %s)%s",
                rid, q["question_id"], result.answer, result.latency_s or 0.0,
                result.crag_verdict, flag
            )

    # --- 6. Compute + write metrics -----------------------------------------
    with open(out / "question_level_results.json", "w") as f:
        json.dump(question_rows, f, indent=2)
    _write_csv(out / "question_level_results.csv", question_rows)

    with open(out / "human_review_queue.json", "w") as f:
        json.dump(human_review_queue, f, indent=2)

    if retrieval_rows:
        retrieval_summary = aggregate_retrieval_metrics(retrieval_rows)
        with open(out / "retrieval_metrics.json", "w") as f:
            json.dump({"per_query": retrieval_rows, "summary": retrieval_summary}, f, indent=2)
        logger.info("retrieval metrics (top_k=%d): %s", pipeline_cfg.top_k, retrieval_summary)

    labelled = [r for r in question_rows if r["gold_answer"]]
    if labelled:
        y_true = [r["gold_answer"] for r in labelled]
        y_pred = [r["answer"] for r in labelled]
        gen_metrics = classification_metrics(y_true, y_pred)
        with open(out / "question_level_llm_metrics.json", "w") as f:
            json.dump(gen_metrics, f, indent=2)
        logger.info("question-level LLM metrics: accuracy=%s, macro_f1=%s",
                    gen_metrics["accuracy"], gen_metrics["macro_f1"])

    # SOTA Faithfulness & Verification Metrics
    total_answered = len(question_rows)
    grounded_count = sum(1 for r in question_rows if r.get("is_evidence_grounded", True))
    crag_correct_count = sum(1 for r in question_rows if r.get("crag_verdict") == "CORRECT")
    crag_reformulated_count = sum(1 for r in question_rows if r.get("crag_reformulated", False))

    sota_metrics = {
        "total_queries": total_answered,
        "evidence_grounding_rate": round(grounded_count / max(1, total_answered), 4),
        "crag_correct_retrieval_rate": round(crag_correct_count / max(1, total_answered), 4),
        "crag_reformulation_rate": round(crag_reformulated_count / max(1, total_answered), 4),
        "unflagged_accuracy_rate": round((total_answered - len(human_review_queue)) / max(1, total_answered), 4),
    }
    with open(out / "sota_faithfulness_metrics.json", "w") as f:
        json.dump(sota_metrics, f, indent=2)
    logger.info("SOTA faithfulness metrics: %s", json.dumps(sota_metrics))

    audit_scores = {
        rid: audit_level_score(answers, pass_threshold_pct=cfg.get("pass_threshold_pct", 70.0))
        for rid, answers in per_report_answers.items()
    }
    with open(out / "audit_level_scores.json", "w") as f:
        json.dump(audit_scores, f, indent=2)

    production_gate = production_readiness_gate(
        cfg, question_rows, aggregate_retrieval_metrics(retrieval_rows) if retrieval_rows else None,
        sota_metrics, gen_metrics if labelled else None,
    )
    with open(out / "production_readiness_gate.json", "w") as f:
        json.dump(production_gate, f, indent=2)
    logger.info("production readiness gate: %s", production_gate["status"])

    with open(out / "run_config.json", "w") as f:
        json.dump({
            "config": cfg, "run_id": run_id, "n_chunks": len(all_chunks),
            "n_errors": n_errors, "n_flagged_for_review": len(human_review_queue),
            "sota_metrics": sota_metrics,
            "source_sha256": {r["report_id"]: _sha256_file(r["path"]) for r in cfg["audit_reports"]},
        }, f, indent=2)

    logger.info("done. All outputs in %s", out)
    return out


def _write_csv(path: Path, rows: List[dict]):
    if not rows:
        return
    flat_rows = []
    for r in rows:
        fr = dict(r)
        for k, v in list(fr.items()):
            if isinstance(v, (list, dict)):
                fr[k] = json.dumps(v)
        flat_rows.append(fr)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(flat_rows[0].keys()))
        writer.writeheader()
        writer.writerows(flat_rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the SOTA audit-assessment evaluation harness.")
    parser.add_argument("--config", required=True, help="Path to eval_config.json")
    parser.add_argument("--out_dir", default="results")
    args = parser.parse_args()
    run_harness(args.config, args.out_dir)
