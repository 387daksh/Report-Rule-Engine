"""Build the twelve black-and-white Objective 3 evidence reports."""

from pathlib import Path
from xml.sax.saxutils import escape

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).parent
OUT = ROOT / "deliverables" / "pdf_source_docx"
PDF_OUT = ROOT / "deliverables" / "pdf"
BLACK = RGBColor(0, 0, 0)


def set_font(run, size=10.5, bold=False, italic=False):
    run.font.name = "Arial"
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), "Arial")
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), "Arial")
    run.font.size = Pt(size)
    run.font.color.rgb = BLACK
    run.bold = bold
    run.italic = italic


def set_cell_margins(cell):
    tc_pr = cell._tc.get_or_add_tcPr()
    mar = tc_pr.first_child_found_in("w:tcMar")
    if mar is None:
        mar = OxmlElement("w:tcMar")
        tc_pr.append(mar)
    for side, value in (("top", 80), ("start", 120), ("bottom", 80), ("end", 120)):
        node = mar.find(qn(f"w:{side}"))
        if node is None:
            node = OxmlElement(f"w:{side}")
            mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def table_geometry(table, widths):
    table.autofit = False
    tbl_pr = table._tbl.tblPr
    for tag, width in (("tblW", sum(widths)), ("tblInd", 120)):
        node = tbl_pr.first_child_found_in(f"w:{tag}")
        if node is None:
            node = OxmlElement(f"w:{tag}")
            tbl_pr.append(node)
        node.set(qn("w:w"), str(width))
        node.set(qn("w:type"), "dxa")
    grid = table._tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in widths:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        grid.append(col)
    for row in table.rows:
        for idx, cell in enumerate(row.cells):
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_w = tc_pr.first_child_found_in("w:tcW")
            if tc_w is None:
                tc_w = OxmlElement("w:tcW")
                tc_pr.append(tc_w)
            tc_w.set(qn("w:w"), str(widths[idx]))
            tc_w.set(qn("w:type"), "dxa")
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell)


def add_para(doc, text, bold=False, italic=False, size=10.5):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.15
    set_font(p.add_run(text), size=size, bold=bold, italic=italic)


def add_table(doc, headers, rows, widths):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table_geometry(table, widths)
    for cell, value in zip(table.rows[0].cells, headers):
        cell.text = ""
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(1)
        set_font(p.add_run(value), size=9, bold=True)
    for values in rows:
        cells = table.add_row().cells
        for cell, value in zip(cells, values):
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.line_spacing = 1.05
            set_font(p.add_run(str(value)), size=9)
    table_geometry(table, widths)
    doc.add_paragraph().paragraph_format.space_after = Pt(1)


def add_bullets(doc, items):
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.line_spacing = 1.1
        set_font(p.add_run(item), size=10.2)


EVIDENCE = [
    "[E1] src/results/1787426063_6d47ba9f8ee0/: saved baseline run artifacts (one report, 12 questions).",
    "[E2] results/modern_retrieval_benchmark.json: Qwen3 retrieval comparison (12 queries, 10 chunks).",
    "[E3] results/qwen3_8b_run/1787660483_900adc72559a/: saved Qwen3-8B single-report run artifacts.",
    "[E4] results/production_real_reports/1787846335_de0ded86a7db/run_config.json and run.log: two-report production-parser run configuration and execution log.",
    "[E5] results/production_real_reports/1787846335_de0ded86a7db/{retrieval_metrics,question_level_llm_metrics,sota_faithfulness_metrics,audit_level_scores}.json: scored metrics and audit decisions.",
    "[E6] sample_data/{2-report.json,4-report.json,real_reports_benchmark_questions.json}: source reports and eight source-derived questions per report.",
    "[E7] Verification executed 28 August 2026: python -m unittest test_json_parser.py test_adaptive_rag.py test_security_gates.py (6 tests passed) and python test_harness_mock.py (offline mock end-to-end passed).",
    "[E8] src/{docling_parser.py,chunking.py,embed_index.py,pipeline.py,evaluation_harness.py,adaptive_rag.py,prompts.py,icl.py}: implementation inspection.",
    "[E9] requirements.txt: declared Python runtime dependencies and optional offline model components.",
    "[E10] results/final_validation/VALIDATION_SUMMARY.md and its cited run directories: controlled local LLM, ICL, prompt, retrieval, CRAG, chunking and chunk-parameter comparisons completed 28 August 2026.",
]

SOURCES = [
    "[S1] Chen et al. (2024), BGE-M3-Embedding, arXiv:2402.03216, https://arxiv.org/abs/2402.03216.",
    "[S2] Santhanam et al. (2021), ColBERTv2, arXiv:2112.01488, https://arxiv.org/abs/2112.01488.",
    "[S3] Faysse et al. (2025), ColPali, arXiv:2407.01449, https://arxiv.org/abs/2407.01449.",
    "[S4] Yang et al. (2025), Qwen3 Technical Report, arXiv:2505.09388, https://arxiv.org/abs/2505.09388.",
    "[S5] Qwen (2025), Qwen3-Reranker-4B model card, https://huggingface.co/Qwen/Qwen3-Reranker-4B.",
    "[S6] Microsoft GraphRAG query documentation, https://microsoft.github.io/graphrag/query/overview/.",
]

DOCS = {
"D01_Literature_and_Technology_Review": {
"title": "D1. Literature and Technology Review",
"purpose": "Technology review for AI-based cybersecurity audit assessment against a benchmark.",
"sections": [
("Scope and conclusion", [
"This review distinguishes published architecture options from work that was actually implemented and tested in this repository. The implemented baseline is a text-first hybrid RAG pipeline; it is not presented as a proven state-of-the-art system. [E8]",
"The practical recommendation is structured hybrid retrieval as the default. Visual retrieval should be enabled only when page images, tables or screenshots are in the accepted input scope; graph retrieval should be reserved for cross-report relationship questions. [S2][S3][S6]"
]),
("Technology comparison", ("table", ["Family", "Contribution", "Project use", "Evidence status"], [
["Dense plus sparse hybrid", "Semantic retrieval plus exact technical terms", "Baseline B0: embeddings, BM25 and rank fusion", "Implemented; saved runs exist [E1][E4]"],
["Cross-encoder reranking", "Second-stage relevance ordering", "Implemented; disabled in the two-report GPU run", "Code inspected; no two-report reranker result [E4][E8]"],
["Qwen3 embedding/reranking", "Modern local retrieval candidates", "Downloaded low-resource models", "Retrieval comparison completed [E2]"],
["Late interaction", "Token-level technical-term matching", "Candidate for identifiers/OCR noise", "Implemented integration point; not evaluated [E8][S2]"],
["Visual document retrieval", "Page/table/screenshot retrieval", "Out of current text-only assessment scope", "CLI path only; not evaluated [E8][S3]"],
["Graph-assisted retrieval", "Finding/entity relationship context", "Optional cross-report route", "Enabled in real-report configuration; no isolated ablation [E4][S6]"]
], [1800, 2700, 2880, 1980])),
("Selection implications", [
"Published capability is not selection evidence. The final choice must be supported by identical corpus, labels, retrieval budget, generator settings, hardware and measured quality/safety metrics. [S1][S4][E8]",
"The present evidence supports using the repository as an auditable proof of concept. It does not support claims of superiority over alternative model families or operational performance on unseen audit agencies. [E4][E5]"
]),
("Evidence and sources", ["Evidence citations used in this report are listed below. External sources describe candidate technologies; repository artifacts support implementation and measured-result statements."])
]},
"D02_LLM_Selection_and_Justification": {
"title": "D2. Candidate LLM Comparison and Selection",
"purpose": "Model-selection evidence, criteria, and provisional recommendation.",
"sections": [
("Decision statement", ["Qwen3-8B is the leading local generator candidate: it reached 81.25% accuracy on the common two-report evaluation, ahead of Qwen2.5-7B at 62.50% and Llama-3-8B at 43.75%. Qwen3-0.6B is not selected because its completed run collapsed to the No class. [E3][E10]", "This is a benchmark-selection result, not a production-selection claim. Independent, balanced multi-report labels are still required. [E10]"]),
("Selection criteria", ("table", ["Criterion", "Why it matters", "Current decision use"], [
["Answer quality", "Benchmark decisions must match gold labels", "Accuracy and macro-F1; class support shown [E5]"],
["Evidence support", "Audit decisions must be traceable", "Grounding rate and valid evidence IDs [E5][E8]"],
["Instruction/JSON reliability", "Automated scoring needs structured output", "Schema-enforced local generation [E8]"],
["Latency and resources", "Offline laptop deployment is constrained", "Mean latency, CPU/GPU fit and model size [E3][E4]"],
["Governance", "Audit data must remain local and reviewable", "Offline serving, config, source and output traceability [E4][E8]"]
], [2100, 3900, 3360])),
("Completed evidence", ("table", ["Configuration", "Corpus", "Observed outcome", "Decision"], [
["Qwen3 embedding/reranker retrieval", "1 report, 12 questions, 10 chunks", "Recall@5=1.00; Precision@5=0.2833; MRR=1.00; nDCG@5=1.00", "Tied B0 on a small corpus [E2]"],
["Qwen3-0.6B end-to-end", "1 report, 12 questions", "Accuracy=58.33%; macro-F1=0.2456; all predictions No", "Do not select [E3]"],
["Qwen3-8B real-report pipeline", "2 reports, 16 questions, 22 chunks", "Accuracy=81.25%; macro-F1=0.4296; 13.66 s mean latency", "Candidate only; benchmark gate remains blocked [E4][E5]"]
], [1950, 2000, 3300, 2110])),
("Justification and limitation", ["Qwen3-8B can run locally with the documented CPU/GPU allocation, and its two-report run completed with no execution errors. That is integration evidence, not comparative superiority: the labels are source-derived, only two reports are included, and Insufficient Evidence has zero support. [E4][E5]", "A final selection should compare Qwen2.5 7B, Qwen3 8B, Qwen3 14B if feasible, and one alternative under frozen prompts, retrieval, questions and hardware. [S4][E8]"]),
("Evidence and sources", ["All numeric claims above are linked to saved metric artifacts [E2]-[E5]."])
]},
"D03_Zero_Shot_and_ICL_Design": {
"title": "D3. Zero-Shot and In-Context Learning Design",
"purpose": "ICL implementation, comparison protocol, and evidence boundary.",
"sections": [
("Implemented strategies", ("table", ["Strategy", "Implementation", "Use"], [
["zero_shot", "Direct assessment prompt with retrieved report evidence", "Baseline without demonstrations"],
["fixed_few_shot", "Fixed examples from the local example bank", "Controls example wording/count"],
["retrieval_few_shot", "Semantically selected examples from icl_example_bank.json", "Current default; k=4 [E4][E8]"]
], [2200, 4100, 3060])),
("Design rationale", ["Examples show the required evidence-first decision pattern: answer Yes, No or Insufficient Evidence; cite retrieved chunks; provide a short justification. The example bank is local and is never treated as audit evidence for the report under assessment. [E8]", "Retrieval-selected examples are a sensible implementation choice because audit questions vary by control, finding and wording. Their use is not yet empirically proven superior to zero-shot or fixed examples. [E4][E8]"]),
("Controlled comparison plan", ("table", ["Variable", "Held constant", "Changed", "Measures"], [
["ICL strategy", "Reports, labels, retrieval context, model, prompt, seed, temperature", "zero-shot / fixed / retrieval", "Accuracy, macro-F1, grounding, abstention safety, latency"],
["Example count", "Same selection policy and examples where applicable", "k = 0, 1, 2, 4, 6", "Quality change and context cost"],
["Example composition", "Question set and evaluation harness", "Positive, negative, missing-evidence, difficult examples", "Per-class F1 and unsafe-answer rate"]
], [1650, 3300, 2200, 2210])),
("What was tested", ["A controlled Qwen2.5-7B comparison completed on the same 16 report-question pairs: zero shot achieved 75.00% accuracy and 0.4697 macro-F1; retrieval few shot k=4 achieved 62.50% and 0.4190; fixed few shot achieved 50.00% and 0.3789. [E10]", "The 28 August verification also passed the offline mock end-to-end path and focused parser, routing/citation, and safety-gate tests. [E7]"]),
("Conclusion", ["Select zero shot as the strongest tested Qwen2.5 ICL condition. It must still be reconfirmed with Qwen3 before it is called the final Qwen3 ICL setting. [E10]"])
]},
"D04_Preprocessing_Chunking_and_Retrieval": {
"title": "D4. Document Preprocessing, Chunking and Retrieval Index",
"purpose": "Implementation report for retrieval over historical cybersecurity audit reports.",
"sections": [
("Implemented processing path", ["Input reports are parsed to provenance-labelled text. Recursive JSON objects and lists are flattened while retaining field paths; duplicate leaf rows are removed; keys containing image or figure are intentionally excluded from this text-only scope. [E8]", "Chunks have stable identifiers and source context. The retrieval path combines dense FAISS search and BM25, fuses rankings, and can apply a reranker before the prompt receives final evidence. [E8]"]),
("Configuration used in the two-report run", ("table", ["Component", "Observed configuration", "Reason / boundary"], [
["Inputs", "2-report.json and 4-report.json", "Two source reports; intermediate Markdown was not indexed [E4][E6]"],
["Chunking", "structure_aware; max 420 tokens; overlap 60; minimum 80", "22 chunks from two reports [E4]"],
["Embedding", "Qwen3-Embedding-0.6B; CUDA:0", "GPU retrieval while generation uses local Qwen3-8B [E4]"],
["Retrieval", "hybrid; top_k=8; candidates_k=60; parent-child and graph enabled", "No isolated ablation for parent-child/graph [E4]"],
["Reranking/verification", "reranker and local claim verifier disabled", "6 GB RTX 4050 resource trade-off [E4]"]
], [1700, 3980, 3680])),
("Routing and evidence controls", ["The adaptive route identifies exact, local and aggregate question modes. Citation IDs must belong to retrieved evidence before a response is considered grounded. Prompt-injection-like report text is detected as untrusted source content. [E7][E8]", "Late interaction and visual retrieval integration points exist but their model weights and visual evaluation have not been completed; neither is claimed as operational evidence. [E8]"]),
("Verification", ["JSON-path preservation and image-context exclusion passed a focused unit test. The offline mock test passed document parsing, chunking, hybrid indexing and metric generation without model downloads. [E7]", "The two-report logged run completed its 16 questions with n_errors=0 and recorded its exact configuration. [E4]"]),
("Conclusion", ["The retrieval index is functional for supplied text/JSON evidence. It is not yet validated for scanned PDFs, screenshots, tables requiring visual reasoning, multilingual reports, or unseen agencies."])
]},
"D05_Retrieval_Evaluation_and_Cases": {
"title": "D5. Retrieval Evaluation and Case Analysis",
"purpose": "Measured retrieval quality with representative successes, failures and limitations.",
"sections": [
("Evaluation setup", ["The strongest saved retrieval evidence is the two-report production-parser run: 16 source-derived questions, 22 structure-aware chunks and top_k=8. Gold chunk identifiers are recorded in the run configuration. [E4][E6]", "Metrics are reported independently of the answer model so retrieval limitations are not hidden by answer accuracy. [E5]"]),
("Measured retrieval metrics", ("table", ["Metric", "Value", "Interpretation"], [
["Precision@8", "0.1443", "Most top-8 context is not gold-labelled; evidence packing can improve."],
["Recall@8 / Hit Rate@8", "0.8750 / 0.8750", "Gold evidence retrieved for 14 of 16 labelled cases."],
["MRR", "0.2781", "Relevant evidence is frequently not ranked near first."],
["nDCG@8", "0.4212", "Ranking quality leaves material room for improvement."],
["Qwen3 comparison recall@5", "1.0000", "On the separate one-report/12-question, 10-chunk benchmark; not directly comparable to the two-report run."]
], [2500, 1500, 5360])),
("Representative cases", ("table", ["Case type", "Observed behaviour", "Implication"], [
["Finding existence / severity / CWE", "Many questions retrieve their labelled finding chunk.", "Structured field paths aid local factual questions [E4][E6]."],
["Negative or universal statement", "Three of four No labels were predicted Yes by the pipeline.", "Need negative/abstention examples and contradiction-aware retrieval [E5]."],
["Missed labelled evidence", "2 of 16 queries had recall@8=0.", "Inspect chunk boundaries, labels and query formulation before increasing k [E5]."],
["Small baseline", "Perfect rank metrics were recorded on a 10-chunk one-report comparison.", "Do not infer generalisation from the easy, overlapping-label setting [E2]."]
], [2100, 3850, 3410])),
("Interpretation", ["High grounding does not repair weak ranking: it means the final cited text is within returned evidence under the implemented check. It is not a claim-entailment guarantee. [E5][E8]", "The next retrieval experiment should freeze reports, questions and labels, then isolate chunk length/overlap, dense-only versus hybrid, reranker, parent-child expansion and graph retrieval."]),
("Evidence", ["Full per-query metrics, including the two recall failures, are preserved in retrieval_metrics.json. [E5]"])
]},
"D06_Prompt_Design_and_Justification": {
"title": "D6. Audit Assessment Prompt Design",
"purpose": "Prompt contract, alternative designs, selection rationale and safety handling.",
"sections": [
("Final prompt contract", ["The selected v2_evidence_review prompt defines an audit-assessment role, supplies a benchmark question and retrieved evidence, and requires a single structured result with answer, supporting evidence, evidence chunk IDs and justification. Answers are constrained to Yes, No or Insufficient Evidence. [E8]", "The structured response also supports claim_evidence and abstention_reason fields for future verification without breaking the required output contract. [E8]"]),
("Prompt alternatives", ("table", ["Version", "Design", "Decision"], [
["v1_direct", "Short direct assessment instruction", "Retained as a comparison implementation [E8]"],
["v2_evidence_review", "Evidence-first JSON response; cites chunk IDs; requires justification", "Selected implementation [E4][E8]"],
["Future verifier prompt", "Claim-by-claim evidence entailment and contradiction check", "Optional implementation path; not calibrated on a large labelled set [E8]"]
], [1900, 4560, 2900])),
("Why v2 is selected", ["The task requires evidence-based answers and traceability to question-level audit decisions. v2 makes the evidence ID part of the machine-readable response, which enables deterministic citation-boundary validation. [E7][E8]", "The two-report run used v2_evidence_review with schema enforcement, temperature 0.0, seed 42 and 384 output tokens. It completed without recorded execution errors. [E4]"]),
("Safety and limitation", ["Report content is evidence, not instruction. Prompt-injection-like text is detected and source boundaries are checked. Unknown citation IDs are rejected. [E7][E8]", "The controlled Qwen2.5 prompt comparison gives v2 62.50% accuracy and v1 56.25%. v2 is retained because it improves the observed control result and preserves the structured evidence contract. [E10]"]),
("Evidence", ["The exact prompt implementation is in src/prompts.py and the use of v2 is captured in run_config.json. [E4][E8]"])
]},
"D07_Integrated_RAG_Chatbot_Prototype": {
"title": "D7. Integrated RAG-Based Audit Assessment Chatbot",
"purpose": "Functional prototype description and verification record.",
"sections": [
("Prototype scope", ["AuditAssessmentPipeline accepts an audit report, a benchmark question and configuration. It returns retrieved evidence IDs/scores, response text, structured answer, CRAG state, grounding state, review flags and configuration metadata. [E8]", "The prototype is local-first: Ollama is used for generation, and the repository does not require upload of project audit data to a cloud API. [E8]"]),
("End-to-end flow", ("table", ["Step", "Component", "Output / control"], [
["1", "Parser and preprocessing", "Provenance-labelled text; image/figure keys excluded [E8]"],
["2", "Chunking and hybrid index", "Stable chunks; dense + BM25 candidates [E8]"],
["3", "Route, retrieve and optionally reformulate", "Exact/local/aggregate route and CRAG verdict [E7][E8]"],
["4", "Prompt and local generation", "Schema-constrained Yes/No/Insufficient Evidence response [E8]"],
["5", "Grounding and audit output", "Evidence IDs, flags, question result and aggregate score [E5][E8]"]
], [700, 3000, 5660])),
("Demonstrated execution", ["The saved two-report run processed 16 report-question pairs and recorded 22 chunks, zero execution errors and zero review flags in the run configuration. [E4]", "The 28 August offline mock test exercised parser fallback, contextual chunking, FAISS/BM25 hybrid retrieval, RRF, mocked reranking/CRAG, schema output, grounding and audit-score calculation. It passed. [E7]"]),
("Use boundary", ["This is a proof-of-concept chatbot, not a validated decision system. It has not demonstrated visual report understanding, broad multilingual coverage, independently reviewed labels, calibrated abstention or a production deployment. [E5][E8]"]),
("Run and trace", ["Offline functional check: from rag/src run python test_harness_mock.py. Saved real-run outputs are in results/production_real_reports/1787846335_de0ded86a7db/. [E4][E7]"])
]},
"D08_Evaluation_Dataset_and_Methodology": {
"title": "D8. Evaluation Dataset and Methodology",
"purpose": "Question set, labelling method, evaluation design and limitations.",
"sections": [
("Dataset registry", ("table", ["Dataset", "Reports", "Questions", "Role"], [
["Initial sample", "sample_report_001.txt", "12", "Baseline/smoke benchmark [E1]"],
["Real JSON proof set", "2-report.json; 4-report.json", "8 per report; 16 total", "Source-derived integration evaluation [E4][E6]"],
["Intermediate Markdown", "2-report_intermediate.md; 4-report_intermediate.md", "0", "Extraction audit artifacts; not duplicate indexed reports [E6]"]
], [2300, 2700, 1800, 2560])),
("Question design", ["The real-report set asks whether reports contain detailed findings, high severity, open status, CWE classifications, remediation, an all-closed statement, timeline evidence, and a no-findings statement. The same eight question templates are applied to both reports. [E6]", "Gold answers and gold chunk IDs are stored per report in the saved run configuration. This supports traceability but is not independent annotation: the question set and labels were derived from the same supplied reports. [E4]"]),
("Method", ("table", ["Layer", "Method", "Reported measures"], [
["Retrieval", "Compare returned chunk IDs with gold chunk IDs", "Precision@k, Recall@k, Hit Rate@k, MRR, nDCG@k [E5]"],
["Question response", "Compare structured answer with gold answer", "Accuracy, per-class metrics, macro-F1, confusion matrix [E5]"],
["Grounding", "Check evidence IDs and lexical support in returned context", "Grounding rate; CRAG measures [E5][E8]"],
["Audit score", "Count Yes answers and apply 70% threshold", "Positive count, percentage, PASS/FAIL [E5]"]
], [1500, 4800, 3060])),
("Limitations and next dataset", ["The 16-pair real-report set has 12 Yes and 4 No gold labels and zero Insufficient Evidence examples. Its macro-F1 cannot establish abstention safety. [E5]", "A credible next evaluation should use report-level train/dev/test separation, independent labels and acceptable evidence spans, multiple agencies and report types, and explicit missing-evidence, contradiction, OCR-noise and visual cases. The planning target is at least 40 reports across VAPT, network, mobile and web/application domains. [E8]"]),
("Conclusion", ["This dataset is suitable for implementation integration and error analysis. It is not sufficient for generalisation or production-quality claims."])
]},
"D09_Automated_Evaluation_Harness": {
"title": "D9. Automated Evaluation Harness",
"purpose": "Reproducible question-level and audit-level evaluation capability.",
"sections": [
("Harness outputs", ("table", ["Artifact", "Contents", "Traceability value"], [
["question_level_results.json / .csv", "Answer, retrieved evidence, scores, CRAG, latency, flags", "Explains each benchmark decision [E5]"],
["retrieval_metrics.json", "Per-query and aggregate ranking measures", "Separates retrieval from LLM quality [E5]"],
["question_level_llm_metrics.json", "Accuracy, macro-F1, per-class metrics, confusion matrix", "Shows class imbalance and errors [E5]"],
["sota_faithfulness_metrics.json", "Grounding and CRAG measures", "Shows evidence-control behaviour [E5]"],
["audit_level_scores.json", "Positive count, percentage, PASS/FAIL", "Traces final audit assessment [E5]"],
["run_config.json and run.log", "Exact configuration, source paths, execution log", "Supports reproduction and audit [E4]"]
], [2460, 3700, 3200])),
("Measured harness run", ["The production-parser run completed 16 pairs across two reports. It used structure-aware chunks, hybrid retrieval, retrieval_few_shot k=4, v2_evidence_review, Qwen3-8B through Ollama, temperature 0.0 and seed 42. [E4]", "It wrote all listed question-level, retrieval, classification, grounding and audit-level artifacts. [E4][E5]"]),
("Release gate", ["The harness contains a production-readiness gate that fails closed unless minimum evidence requirements are satisfied, including independent balanced labels with Insufficient Evidence support and quality thresholds. The current two-report proof set is therefore not production evidence. [E8]", "The focused safety test confirms that a one-report, one-positive-label input cannot pass that gate. [E7]"]),
("Verification", ["The offline mock harness was rerun on 28 August 2026 and passed end to end. It is intentionally a mock-based functional check; it does not validate live-model quality. [E7]"]),
("Conclusion", ["The harness delivers the audit trail requested by the assignment. Its limiting factor is evaluation data quality and size, not the absence of structured outputs."])
]},
"D10_Results_and_Error_Analysis": {
"title": "D10. Evaluation Results and Error Analysis",
"purpose": "Quantitative outcomes, difficult cases and truthful interpretation.",
"sections": [
("Primary result: two-report JSON proof set", ("table", ["Measure", "Observed value", "Meaning"], [
["Report-question pairs / chunks", "16 / 22", "Small integration dataset [E4]"],
["Answer accuracy / macro-F1", "81.25% / 0.4296", "Macro-F1 limited by No errors and zero abstention support [E5]"],
["Precision@8 / Recall@8", "14.43% / 87.50%", "Evidence is often found but weakly ranked [E5]"],
["MRR / nDCG@8", "0.2781 / 0.4212", "Relevant evidence is not consistently near the top [E5]"],
["Grounding / CRAG-correct", "100% / 25.00%", "Citation-boundary pass is not semantic entailment [E5][E8]"],
["CRAG reformulation / mean latency", "68.75% / 13.66 s", "Retrieval judge is frequently uncertain; end-to-end latency is measurable [E5]"]
], [2200, 1850, 5310])),
("Audit-level output", ("table", ["Report", "Positive / total", "Score", "Decision"], [
["2-REPORT", "8 / 8", "100.00%", "PASS at 70% threshold [E5]"],
["4-REPORT", "7 / 8", "87.50%", "PASS at 70% threshold [E5]"]
], [2300, 2200, 2200, 2660])),
("Error analysis", ["The answer confusion matrix contains 12 correct Yes responses, one correct No response and three No-to-Yes errors. This makes universal or negative report statements the highest-priority failure type. [E5]", "Two queries have zero recall@8. Raising the context limit alone would conceal the diagnosis; inspect gold labels, chunk boundaries and query formulation, then run isolated retrieval ablations. [E5]", "The grounder checks evidence-boundary/lexical support, so 100% grounding should not be reported as proof that every answer is entailed by the cited passage. [E5][E8]"]),
("Related saved results", ["The separate Qwen3 retrieval comparison tied B0 on a very small one-report corpus. The Qwen3-0.6B end-to-end run achieved 58.33% accuracy and predicted No for all questions, showing that a newer/smaller generator is not automatically a better choice. [E2][E3]", "The two-report proof is a useful integration result but not a production reliability study. [E4][E5]"]),
("Priority actions", ["Add independently reviewed No and Insufficient Evidence labels; calibrate CRAG; compare chunk/retrieval variants under a frozen test; evaluate claim entailment and contradiction handling."])
]},
"D11_Integrated_Proof_of_Concept": {
"title": "D11. Integrated Proof of Concept",
"purpose": "End-to-end benchmark-based assessment demonstration using supplied audit reports.",
"sections": [
("Demonstration objective", ["Demonstrate that the system can take an extracted cybersecurity audit report and benchmark questions, retrieve report evidence, issue structured decisions, and aggregate those decisions into an audit score with a reproducible trail. [E4][E5]", "The demonstration uses two supplied JSON reports and not a synthetic substitute. It intentionally excludes image/figure context from the text-only submission scope. [E4][E6][E8]"]),
("Demonstrated configuration", ("table", ["Stage", "Proof configuration", "Recorded result"], [
["Input", "2-report.json and 4-report.json; eight questions each", "16 report-question pairs [E4][E6]"],
["Evidence index", "22 structure-aware chunks; Qwen3 embedding; hybrid top-8 retrieval", "Per-query evidence saved [E4][E5]"],
["Assessment", "Qwen3-8B local Ollama; v2 prompt; schema enforcement; temperature 0", "Answers and latencies saved [E4][E5]"],
["Aggregation", "70% pass threshold", "Both reports produced PASS scores [E5]"]
], [1400, 5000, 2960])),
("Outcome", ["The run completed with no recorded execution errors. It achieved 81.25% answer accuracy, 87.50% Recall@8, 100% grounding under the implemented check, and 13.66-second mean latency. [E4][E5]", "The reranker and claim verifier were disabled in this run to avoid competing with Qwen3-8B for the 6 GB laptop GPU. This is a documented hardware configuration, not evidence that those controls are unnecessary. [E4]"]),
("Reproduction and verification", ["Saved live artifacts: results/production_real_reports/1787846335_de0ded86a7db/. Offline functional demonstration: from rag/src, run python test_harness_mock.py. Focused parser, routing/citation and release-gate tests passed on 28 August 2026. [E4][E7]", "Reproduction of the live run also requires the stated local model weights and Ollama service; it should remain in the approved air-gapped environment. [E4]"]),
("Proof boundary", ["This POC demonstrates an auditable integration path. It does not establish a production release, comparative model superiority, visual understanding, or generalisation beyond the two supplied reports."])
]},
"D12_Final_Technical_Report_and_Demo": {
"title": "D12. Final Technical Report and Demonstration",
"purpose": "Consolidated conclusion, deliverable map and 5-10 minute technical demo script.",
"sections": [
("Final conclusion", ["The submitted system is a local, evidence-traceable proof of concept for benchmarking individual cybersecurity audit reports. It can parse supplied JSON reports, retrieve source evidence, produce structured Yes/No/Insufficient Evidence decisions, retain question-level outputs and compute an audit-level score. [E4][E5][E8]", "The strongest measured real-report result is 81.25% accuracy across 16 source-derived question/report pairs, with Recall@8 of 87.50%, Precision@8 of 14.43%, MRR of 0.2781, nDCG@8 of 0.4212, 100% implemented grounding rate and 13.66-second mean latency. [E5]", "These results are implementation/integration evidence only. The dataset has two reports, 12 Yes labels, four No labels and zero Insufficient Evidence labels; therefore it cannot support a production or generalisation claim. [E5]"]),
("Deliverable status", ("table", ["Work package", "Delivered evidence", "Status"], [
["WP1: LLM and ICL", "D1-D3: candidate review, criteria, ICL implementations and controlled comparison plan", "Implemented; comparative ICL/model evidence incomplete [E2][E3]"],
["WP2: Retrieval and chatbot", "D4-D7: parser, chunker, hybrid index, prompt, pipeline and offline check", "Functional proof of concept [E7][E8]"],
["WP3: Evaluation", "D8-D11: labelled questions, harness, artifacts, metrics, error analysis and two-report POC", "Measured integration evidence; release gate blocked [E4][E5]"]
], [2050, 4840, 2470])),
("Recommended 5-10 minute demo", ("table", ["Time", "Demonstration step", "Evidence to show"], [
["0:00-1:00", "State objective, benchmark scoring flow and air-gapped constraint", "This report and D1"],
["1:00-2:30", "Show parser, structured chunks and hybrid retrieval design", "D4; src module map [E8]"],
["2:30-4:00", "Show v2 evidence-first prompt and one question-level record", "D6; question_level_results.json [E5]"],
["4:00-5:30", "Show two-report metrics and audit scores", "D10; metric and score JSON [E5]"],
["5:30-7:00", "Run or explain offline mock verification", "D7/D9; 28 Aug test record [E7]"],
["7:00-9:00", "Explain limitations, release gate and next experiment", "D8-D10; blocked evidence boundary [E5]"]
], [1100, 4280, 3980])),
("Next work justified by the results", ["First, independently label a report-level held-out set with enough No and Insufficient Evidence cases. Second, run controlled ablations of ICL, chunking, hybrid retrieval, reranking and CRAG. Third, evaluate claim entailment, contradictions, OCR noise and visual evidence if that input scope is accepted. [E5][E8]", "Do not add late interaction, graph or visual complexity by default. Each should be selected only if it improves the frozen evaluation under its intended question type. [S2][S3][S6]"]),
("Evidence and external sources", ["The following repository artifacts and literature sources substantiate this report. No external source is used to claim an unmeasured project result."])
]},
}

SUPPLEMENTS = {
    "D06_Prompt_Design_and_Justification": [
        "Prompt design is not a cosmetic part of this system. The prompt is the control plane between retrieved audit evidence and the audit-level score, so it must force the model to expose the answer category, quoted support and source identifiers in a form the harness can validate. A prose-only answer would be easier to demo but would break traceability and make error analysis much weaker. [E5][E8]",
        "The prompt also makes missing evidence a first-class result rather than an error condition. This matters for audit assessment because an unsupported positive claim can falsely inflate the final score. The present dataset cannot yet measure abstention quality because it has no Insufficient Evidence gold examples; the implementation already reserves the category and the next benchmark must evaluate it directly. [E5][E8]",
        "For operational use, prompt versions should remain frozen during every comparative experiment. Any change to instructions, schema, demonstration count or evidence format must be logged alongside model, retrieval, seed and question-set changes. The current harness design supports that discipline through stored configuration and question-level artifacts. [E4][E8]",
    ],
    "D07_Integrated_RAG_Chatbot_Prototype": [
        "The prototype is intentionally engineered as a sequence of inspectable components rather than a single opaque agent. That makes failures diagnosable: a reviewer can determine whether an incorrect audit decision came from parsing, chunking, retrieval, evidence selection, prompt compliance or answer generation. The saved results preserve enough intermediate data to conduct that diagnosis without replaying the entire model run. [E4][E5][E8]",
        "This separation is particularly useful on constrained offline hardware. The two-report configuration documents which components were enabled and which were deliberately disabled to avoid GPU memory contention. The generator, retrieval settings and evidence controls can therefore be tuned independently instead of forcing a one-size-fits-all configuration that is slow, fragile or impossible to reproduce. [E4][E9]",
        "A production extension should preserve this shape: retain the deterministic evidence and scoring layers, then strengthen the parser, labels and verification thresholds. The right next step is not a more elaborate chat UI; it is a larger independently reviewed corpus that can demonstrate whether the existing controls improve real audit-assessment reliability. [E5][E8]",
    ],
    "D09_Automated_Evaluation_Harness": [
        "The harness is a substantive deliverable, not merely a script that prints an accuracy number. It creates the evidence chain needed to challenge an audit score: the report and question are identifiable, the retrieved chunks and model response are retained, the configuration is frozen, and the aggregate score can be reconstructed from individual Yes/No/Insufficient Evidence decisions. [E4][E5][E8]",
        "Its metric design is deliberately multi-layered. Retrieval quality, answer correctness, grounding behaviour, CRAG behaviour and audit score are measured separately because they answer different questions. A high answer score with weak retrieval should prompt investigation, while a high grounding rate without balanced labels should not be mistaken for validated safety. [E5]",
        "The release gate provides an important engineering safeguard: it converts missing benchmark evidence into an explicit BLOCKED result instead of a silent go-live assumption. The current proof therefore has a defensible outcome: the harness works and produces reproducible results, but the available data does not yet meet the evidence threshold for a production-quality claim. [E7][E8]",
    ],
}

TAILORED_SECTIONS = {
    "D01_Literature_and_Technology_Review": [
        ("What was reviewed and why", ["This deliverable is a technology review, not an experiment report. It asks which RAG capabilities matter for evidence-bound cybersecurity assessment: provenance-preserving parsing, hybrid retrieval, controlled generation, and measurable evaluation. The review separates published approaches from repository implementation and from completed measurements so a reader can see both ambition and evidence. [E8][S1][S2]", "The recommended architecture is a practical layered design rather than a claim that every new RAG component should be switched on. Text/JSON evidence comes first; visual retrieval is justified only for page-only evidence; graph retrieval is justified only for relationship or cross-report questions. This avoids expensive components where a local factual lookup is sufficient. [S2][S3][S6]"]),
        ("Evidence maturity of reviewed technologies", ("table", ["Technology", "Published rationale", "Project status"], [["Hybrid dense + BM25 retrieval", "Semantic and exact-term retrieval complement each other", "Implemented and ablated [E10]"], ["Modern Qwen embedding", "Local multilingual retrieval candidate", "Used in completed runs [E4][E10]"], ["Cross-encoder reranking", "Improves final relevance ordering", "Implemented; not enabled in 6 GB production run [E8]"], ["Late interaction / visual RAG", "Useful for technical phrase or page-layout evidence", "Integration path only; not a measured claim [E8][S2][S3]"], ["Graph-assisted retrieval", "Useful for entity and cross-report relations", "Optional route; no isolated effectiveness claim [E4][S6]"]], [2600, 3500, 3260])),
    ],
    "D02_LLM_Selection_and_Justification": [
        ("Controlled model selection result", ("table", ["Model", "Accuracy", "Macro-F1", "Grounding", "Mean latency", "Selection meaning"], [["Qwen3 8B", "81.25%", "0.4296", "100.00%", "13.66 s", "Leading local candidate"], ["Qwen2.5 7B", "62.50%", "0.4190", "100.00%", "15.16 s", "Stable control model"], ["Llama 3 8B", "43.75%", "0.2456", "56.25%", "44.66 s", "Not selected"]], [1200, 950, 950, 1050, 1050, 4160])),
        ("Selection rationale", ["Qwen3-8B is selected as the leading benchmark candidate because it produced the strongest answer accuracy and retained the evidence-grounding check on the same two-report workload. This is a concrete decision based on completed local runs, not on a model-card claim. [E10]", "The choice remains deployment-provisional because the test corpus is small and source-derived. The correct conclusion is that Qwen3-8B is the best observed candidate for this proof of concept, while independent expert labels are required before declaring a production winner. [E10]"]),
    ],
    "D03_Zero_Shot_and_ICL_Design": [
        ("ICL experiment and design decision", ("table", ["Configuration", "Examples supplied", "Accuracy", "Macro-F1", "Decision"], [["Zero shot", "No demonstrations", "75.00%", "0.4697", "Best Qwen2.5 control result"], ["Retrieval few shot", "4 semantically selected local examples", "62.50%", "0.4190", "Works; not selected on this control"], ["Fixed few shot", "Fixed local examples", "50.00%", "0.3789", "Not selected"]], [2100, 2450, 1250, 1250, 2310])),
        ("Why examples remain a controlled variable", ["Few-shot examples are not report evidence. They are local formatting and reasoning demonstrations, selected separately from the retrieved audit report. Keeping that boundary explicit prevents an ICL example from silently introducing facts into an assessment answer. [E8][E10]", "The observed zero-shot result means the present four-example bank did not improve this small Qwen2.5 evaluation. The final Qwen3 configuration retains retrieval few shot only as the existing production-shaped setting; zero shot should be retested with Qwen3 before a cross-model ICL conclusion is made. [E10]"]),
    ],
    "D04_Preprocessing_Chunking_and_Retrieval": [
        ("Data-to-evidence architecture", ["The retrieval layer begins with evidence preservation, not embeddings. The JSON parser flattens nested findings while retaining field paths and report identity, so a chunk can be linked back to the report structure used by an auditor. Image and figure fields are deliberately excluded because this submission does not claim visual understanding. [E6][E8]", "The index combines dense vectors for semantic paraphrase with BM25 for exact security vocabulary. This is a strong fit for audit reports, where a question may use general language while the underlying report contains exact values such as CWE identifiers, severity labels, dates or remediation status. [E8][E9]"]),
        ("Chunking investigation", ("table", ["Configuration", "Chunks", "Accuracy", "Macro-F1", "Interpretation"], [["Fixed 240 / overlap 30", "24", "62.50%", "0.4190", "More fragments; no accuracy gain"], ["Fixed 420 / overlap 60", "14", "75.00%", "0.5253", "Best tested Qwen2.5 setting"], ["Fixed 600 / overlap 90", "11", "62.50%", "0.4889", "Larger context; parse/review issues"], ["Contextual 420 / overlap 60", "22", "37.50%", "0.3294", "Not selected"]], [2100, 900, 1100, 1100, 4160])),
    ],
    "D05_Retrieval_Evaluation_and_Cases": [
        ("Retrieval ablation result", ("table", ["Retrieval setup", "Accuracy", "Grounding", "Recall@8", "MRR", "Reading"], [["Dense-only", "50.00%", "87.50%", "87.50%", "0.3693", "Ranks labelled chunks better but lower answer quality"], ["Hybrid dense + BM25", "62.50%", "100.00%", "87.50%", "0.2781", "Selected practical configuration"]], [1850, 1000, 1100, 1000, 900, 3510])),
        ("Case analysis method", ["Retrieval is assessed independently from the generated answer. The harness records each returned chunk ID and compares it with the stored gold chunk IDs for the unchanged structure-aware boundaries. This gives 87.50% Recall@8: evidence was missed for two of sixteen labelled cases. [E5][E10]", "The dense-only result shows why no single ranking metric is enough: it produced stronger MRR/nDCG but weaker answer accuracy and grounding. Hybrid retrieval is selected for the current POC because it better supports the end-to-end assessment outcome, while future experiments should add independently annotated evidence spans. [E10]"]),
    ],
    "D06_Prompt_Design_and_Justification": [
        ("Prompt comparison and final contract", ("table", ["Prompt", "Core instruction", "Accuracy", "Output control", "Decision"], [["v1_direct", "Directly answer from retrieved evidence", "56.25%", "Less explicit evidence review", "Comparison baseline"], ["v2_evidence_review", "Answer, evidence IDs, support and justification", "62.50%", "Schema-constrained JSON", "Selected"]], [1500, 3300, 1100, 1800, 1660])),
        ("Why the final prompt is fit for audit scoring", ["The final response contract is intentionally restrictive: Yes, No or Insufficient Evidence; supporting evidence; valid retrieved chunk IDs; and a concise justification. That gives the scoring harness a stable output and prevents a fluent but untraceable paragraph from becoming an audit decision. [E8][E10]", "v2 is selected both because it scored better on the controlled Qwen2.5 run and because it meets the assignment's mandatory evidence-based response requirement. Prompt injection in source text is treated as untrusted report content, while invalid citations are rejected by deterministic checks. [E7][E10]"]),
    ],
    "D07_Integrated_RAG_Chatbot_Prototype": [
        ("Prototype architecture", ("table", ["Stage", "Responsible module", "What it contributes"], [["Parse", "docling_parser.py", "Preserves report text and provenance paths"], ["Retrieve", "chunking.py + embed_index.py", "Builds chunks and hybrid evidence candidates"], ["Assess", "pipeline.py + prompts.py", "Routes question and obtains structured local answer"], ["Guard", "adaptive_rag.py", "Validates citation/evidence controls and source safety"], ["Score", "evaluation_harness.py", "Records results and creates audit decision"]], [1200, 2600, 5560])),
        ("Why this is a genuine integrated prototype", ["The demonstration is not a disconnected collection of utilities. One run starts from supplied JSON reports, generates evidence-bearing question responses, calculates retrieval and answer measures, and writes audit-level PASS/FAIL outputs. The two-report run completed all 16 pairs with its configuration and source hashes saved. [E4][E5]", "The local-first stack is suitable for sensitive reports: Python performs parsing/indexing/evaluation, FAISS and BM25 perform retrieval, and Ollama serves the generator locally. The design can be inspected component by component if an audit decision is challenged. [E4][E8][E9]"]),
    ],
    "D08_Evaluation_Dataset_and_Methodology": [
        ("Label distribution and scope", ("table", ["Element", "Current value", "Methodological consequence"], [["Source reports", "2 extracted JSON reports", "Integration evidence only"], ["Report-question pairs", "16", "Too small for stable generalisation estimates"], ["Gold answers", "12 Yes; 4 No; 0 Insufficient Evidence", "Macro-F1 and abstention safety are limited"], ["Evidence labels", "Gold chunk IDs for structure-aware 420/60", "Rank metrics are invalid after boundary changes"], ["Decision threshold", "70% positive answers", "Reproducible POC score, not expert certification"]], [2300, 2600, 4460])),
        ("Evaluation integrity", ["Questions were derived from the actual supplied reports and applied consistently to both reports. The harness stores per-report answer labels and evidence IDs, avoiding a synthetic task that bears no relation to the documents being assessed. [E4][E6]", "The limitation is equally important: source-derived labels are not independent expert labels. The package therefore uses a release gate that correctly remains BLOCKED until a larger balanced, independently reviewed corpus exists. [E7][E10]"]),
    ],
    "D09_Automated_Evaluation_Harness": [
        ("Reproducibility contract", ("table", ["Record", "Captured by harness", "Why a reviewer needs it"], [["Input identity", "Report ID, source hash and question ID", "Connects a score to immutable inputs"], ["Retrieval trace", "Chunk IDs, scores and CRAG state", "Explains what evidence reached the model"], ["Generation trace", "Model, prompt, seed, temperature and response", "Supports controlled reruns"], ["Scoring trace", "Gold answer, correctness, grounding and audit roll-up", "Separates local error from final decision"], ["Release gate", "Report/label/quality thresholds", "Blocks overclaiming from small evidence"]], [1900, 3900, 3560])),
        ("Harness behaviour demonstrated", ["The completed runs produce JSON and CSV question-level records, retrieval and classification metric files, faithfulness measures, audit scores, logs and exact configurations. This directly meets the requirement to trace every final audit score to its benchmark questions and evidence. [E4][E5][E10]", "The production-readiness gate is deliberately stricter than the POC scorer. A report may score PASS against the selected benchmark while the evidence package is still BLOCKED from a production claim because the evaluation corpus is insufficient. [E5][E10]"]),
    ],
    "D10_Results_and_Error_Analysis": [
        ("Observed error taxonomy", ("table", ["Failure pattern", "Observed evidence", "Response"], [["No interpreted as Yes", "3 of 4 No labels missed in the Qwen3 real-report run", "Add negative and contradiction-focused labels"], ["Missing-evidence safety unmeasured", "No Insufficient Evidence gold examples", "Create independently labelled abstention cases"], ["Weak evidence ranking", "Recall@8=87.50%; MRR=0.2781 in Qwen3 run", "Inspect query/chunk evidence and retriever variants"], ["Malformed structured output", "Contextual and large-window conditions produced parse/review flags", "Retain schema checks and avoid unvalidated settings"]], [2200, 4000, 3160])),
        ("Interpretation of the headline result", ["The 81.25% Qwen3 accuracy is a useful POC result because it comes from a real executed two-report workflow, not an illustrative demo. It is not enough to claim reliable assessment across unseen agencies, report formats or missing-evidence cases. [E4][E5][E10]", "The architecture's value is that these limitations are visible. The harness surfaces ranking metrics, response errors, flags and class imbalance instead of presenting only the headline audit score. [E5][E10]"]),
    ],
    "D11_Integrated_Proof_of_Concept": [
        ("Demonstration acceptance trail", ("table", ["Proof step", "Evidence produced", "Completion"], [["Load two reports", "Source hashes and 22 chunks", "Completed [E4]"], ["Ask benchmark questions", "16 structured question-level records", "Completed [E5]"], ["Validate evidence", "Grounding, CRAG and review fields", "Completed [E5]"], ["Aggregate score", "2-REPORT 100%; 4-REPORT 87.5%", "Completed [E5]"], ["Prevent premature release", "Production readiness gate BLOCKED", "Completed [E10]"]], [2000, 4700, 2660])),
        ("What the proof demonstrates", ["The POC demonstrates an auditable benchmark-assessment workflow from source report through retrieval to an aggregate result. The key contribution is not merely that a model can answer questions: every answer can be inspected together with the evidence, configuration and resulting score. [E4][E5]", "It intentionally does not demonstrate a production system. The proof set is too small, visual evidence is outside scope, and the release gate therefore protects the integrity of the submission conclusion. [E8][E10]"]),
    ],
    "D12_Final_Technical_Report_and_Demo": [
        ("What a reviewer can verify", ("table", ["Review question", "Where the submission answers it"], [["Why this architecture?", "D1 and D4: technology rationale, provenance and hybrid retrieval"], ["Which model/configuration was tested?", "D2, D3 and D6: controlled model, ICL and prompt outcomes"], ["Does retrieval actually work?", "D5: metrics and evidence-case analysis"], ["Can it be reproduced?", "D9 and final_validation ledger: configs, logs and outputs"], ["What does the POC prove and not prove?", "D10 and D11: results, errors, gate and limitations"]], [2700, 6660])),
        ("Final submission position", ["This is a strong technical POC submission because it combines a modern local RAG architecture with a traceable evaluation harness and actual controlled experiments. It tells a coherent story from research rationale to implementation to comparative evidence, instead of treating the model as a black box. [E8][E10]", "The final spoken demo should lead with the auditable chain: report -> provenance-preserving evidence -> hybrid retrieval -> constrained answer -> question-level record -> audit score -> release gate. Finish by stating the precise next requirement: independent expert labels across more reports. [E4][E5][E10]"]),
    ],
}

# Final-review exhibits are deliberately different for each deliverable.  They
# expose the evidence a reviewer needs, rather than repeating a project summary.
FINAL_REVIEW_EXHIBITS = {
    "D01_Literature_and_Technology_Review": [
        ("Technology adoption decision", ("table", ["Capability", "Decision for this POC", "Reason and review condition"], [["Hybrid retrieval", "Adopt", "Completed dense-only versus hybrid comparison improved answer accuracy from 50.00% to 62.50%. [E10]"], ["Evidence-first prompting", "Adopt", "v2 improved the Qwen2.5 control and makes evidence IDs machine-checkable. [E10]"], ["Reranking", "Defer", "Code path exists, but it was disabled for the 6 GB laptop run; no claimed benefit. [E4][E8]"], ["Visual / graph retrieval", "Constrain", "Visual input is outside scope; graph route has no isolated effectiveness result. [E4][E8]"]], [1900, 1950, 5510])),
        ("Review conclusion", ["The technical position is intentionally selective. The submission does not portray every available RAG component as an achievement; it adopts only components supported by a concrete need or a completed local comparison. This makes the architecture credible for an audit-review setting, where explainability and repeatability matter more than novelty. [E8][E10]", "The resulting research conclusion is that a local, provenance-preserving hybrid RAG design is a defensible POC foundation. Reranking, visual retrieval and richer graph reasoning remain bounded future experiments with their own acceptance criteria, not implied production features."]),
    ],
    "D02_LLM_Selection_and_Justification": [
        ("Final model decision ledger", ("table", ["Model", "Accuracy / macro-F1", "Grounding / latency", "Selection outcome"], [["Qwen3 8B", "81.25% / 0.4296", "100.00% / 13.66 s", "Leading POC candidate"], ["Qwen2.5 7B", "62.50% / 0.4190", "100.00% / 15.16 s", "Control baseline"], ["Llama 3 8B", "43.75% / 0.2456", "56.25% / 44.66 s", "Not selected"], ["Qwen3 0.6B", "58.33% / 0.2456", "All predictions No", "Not selected"]], [1500, 1900, 2100, 3860])),
        ("How to read the decision", ["Qwen3-8B wins the observed trade-off: it is the highest-accuracy candidate and is faster than the two comparison models in the logged 16-pair run. The selection is therefore evidence-backed for the current hardware and evaluation configuration, rather than based only on model-family reputation. [E10]", "However, the No class has recall of 0.25 (one correct No out of four) and the dataset contains no Insufficient Evidence examples. The final report must state this directly: Qwen3-8B is selected for the POC implementation, while production selection remains pending an independently labelled, balanced evaluation set. [E5][E10]"]),
    ],
    "D03_Zero_Shot_and_ICL_Design": [
        ("Worked in-context example pattern", ("table", ["Question", "Evidence", "Required verdict", "Why this matters"], [["Are backups tested quarterly?", "Backups complete nightly; restore testing is not mentioned.", "Insufficient Evidence", "Demonstrates that silence is not a Yes or No claim."], ["Is segmentation implemented?", "Payment subnet is reachable from corporate VLAN without an ACL.", "No", "Demonstrates a contradiction-backed negative answer."], ["Is password rotation enforced?", "Privileged accounts rotate every 60 days.", "Yes", "Demonstrates threshold-based evidence use."]], [2000, 3100, 1600, 2660])),
        ("Review conclusion", ["The example bank defines output behaviour; it must never be mistaken for evidence about the report being assessed. The worked patterns cover affirmative, negative and missing-evidence cases so the model sees the required answer format without being given facts from the target audit report. [E8]", "On the frozen Qwen2.5 control, adding the present examples did not improve accuracy: zero shot 75.00%, retrieval few shot 62.50%, fixed few shot 50.00%. The defensible decision is to retain zero shot as the tested control winner and label Qwen3 ICL selection as a required follow-up, not as an assumed transfer. [E10]"]),
    ],
    "D04_Preprocessing_Chunking_and_Retrieval": [
        ("Evidence lineage reviewed", ("table", ["Stage", "Concrete output", "Reviewer check"], [["Input", "2-report.json and 4-report.json", "Only supplied JSON reports were indexed; intermediate Markdown was excluded."], ["Parse", "Provenance-labelled paths", "Nested fields remain attributable to report structure; image/figure keys excluded."], ["Chunk", "22 structure-aware chunks", "IDs are retained in run configuration and question-level records."], ["Retrieve", "Top-8 hybrid evidence candidates", "Returned IDs/scores are available for every question."], ["Generate", "Schema-bound response", "Cited IDs must be in the retrieved set. [E4][E5]"]], [1050, 3300, 5010])),
        ("Configuration decision", ["The real-report pipeline uses a structure-aware 420-token/60-token overlap configuration because audit evidence is naturally organised as nested findings and recommendations. That arrangement preserves report context while allowing question-level provenance. [E4][E8]", "The separate fixed-window experiment is valuable, not contradictory: 420/60 fixed chunks achieved 75.00% answer accuracy on the Qwen2.5 control, versus 62.50% for structure-aware chunks. It is not automatically substituted into the Qwen3 run because the existing gold evidence IDs are tied to structure-aware boundaries; changing them without re-authoring labels would corrupt the retrieval comparison. [E10]"]),
    ],
    "D05_Retrieval_Evaluation_and_Cases": [
        ("Question-level retrieval exhibits", ("table", ["Question / report", "Gold evidence retrieved?", "Observed implication"], [["RQ1 detailed findings / 2-REPORT", "Yes; rank 4", "The correct evidence is available, but not first-ranked."], ["RQ7 timeline / 4-REPORT", "Yes; rank 1", "A report-structure question can be efficiently answered."], ["RQ1 detailed findings / 4-REPORT", "No; Recall@8 = 0", "A correct answer may not prove retrieval success; inspect evidence separately."], ["RQ5 remediation / 4-REPORT", "No; Recall@8 = 0", "Second concrete recall miss requiring chunk/query review."]], [2450, 2050, 4860])),
        ("Evaluation judgement", ["The retrieval result is mixed but informative: Recall@8 is 87.50%, while MRR is 0.2781 and nDCG@8 is 0.4212. The evidence is usually somewhere in the eight returned chunks, but often not near the top. This is a real limitation for an audit assessor because extra context increases the chance of the generator selecting an irrelevant statement. [E5]", "Hybrid retrieval is retained only as the better end-to-end control configuration: it improved accuracy to 62.50% and grounding to 100.00%, compared with dense-only 50.00% and 87.50%. These figures do not prove it is universally best; they justify the current POC choice and define the next ablation. [E10]"]),
    ],
    "D06_Prompt_Design_and_Justification": [
        ("Final response schema", ("table", ["Field", "Purpose", "Validation rule"], [["answer", "Benchmark decision", "Only Yes, No or Insufficient Evidence."], ["supporting_evidence", "Short report-grounded quote/paraphrase", "Empty when evidence is insufficient."], ["evidence_chunk_ids", "Links decision to returned context", "Every ID must belong to retrieved evidence."], ["justification", "Explains evidence-to-verdict link", "One or two concise sentences."], ["abstention_reason", "Makes uncertainty explicit", "Required for an Insufficient Evidence outcome."]], [1850, 4050, 3810])),
        ("Prompt-selection judgement", ["The v2 prompt is not simply longer wording. It adds an explicit evidence-review instruction before the schema response, asks the model to cite only checked chunks, and separates abstention from unsupported guessing. Those instructions are aligned with the assignment's requirement to preserve evidence behind a benchmark decision. [E8]", "Under the Qwen2.5 control, v2 scored 62.50% accuracy versus 56.25% for v1. It is therefore selected because it improves the observed score and enables deterministic validation; it is not claimed to solve factual entailment, especially where retrieved context is incomplete. [E7][E10]"]),
    ],
    "D07_Integrated_RAG_Chatbot_Prototype": [
        ("Integrated execution evidence", ("table", ["Input / control", "Recorded result", "Why it proves integration"], [["2 JSON audit reports", "22 chunks created", "Demonstrates ingestion and index construction."], ["16 benchmark questions", "16 structured records; n_errors = 0", "Demonstrates complete question loop."], ["Local Qwen3 8B", "81.25% accuracy; 13.66 s mean latency", "Demonstrates local generation under saved configuration."], ["Evidence guard", "100% grounding rate; 0 review flags", "Demonstrates citation-boundary validation."], ["Audit aggregation", "100% and 87.5% report scores", "Demonstrates report-level decision output. [E4][E5]"]], [2000, 2600, 5110])),
        ("Prototype review conclusion", ["The integrated result matters because all stages are connected in one run: source report identity, chunks, retrieval, prompt, model response, evidence IDs and final score are written together. A reviewer can start at a report-level PASS and inspect the corresponding question and retrieved text rather than trusting a dashboard total. [E4][E5]", "This prototype does not yet establish a deployable chatbot. It requires independently labelled reports, visual-document evaluation, calibrated abstention, and stress testing before it can be used beyond a controlled POC. [E8][E10]"]),
    ],
    "D08_Evaluation_Dataset_and_Methodology": [
        ("Controlled-comparison contract", ("table", ["When comparing", "Held constant", "Changed variable"], [["LLMs", "Reports, 16 pairs, labels, retrieval budget, prompt schema, seed", "Generator model"], ["ICL", "Reports, labels, retrieval, Qwen2.5 control, seed", "Example-selection strategy"], ["Prompts", "Reports, labels, retrieval, Qwen2.5 control, seed", "v1 direct versus v2 evidence review"], ["Retrieval", "Reports, labels, generator, top-8, prompt", "Dense-only versus hybrid"], ["Chunking", "Reports, questions, answer labels and generator", "Chunk boundaries and window parameters"]], [1400, 4950, 3360])),
        ("Methodological judgement", ["This protocol is stronger than an illustrative chatbot demo because every comparison declares what was held constant and records a run-specific configuration and log. It permits a reviewer to distinguish a model change from a retrieval, prompt or data change. [E10]", "The protocol still has a hard validity boundary: both the questions and gold labels are source-derived from two supplied reports. The evidence can support component selection for this POC; it cannot support claims about real-world accuracy, missing-evidence safety or generalisation across audit agencies. [E5][E10]"]),
    ],
    "D09_Automated_Evaluation_Harness": [
        ("Score-to-evidence trace", ("table", ["Trace level", "Saved record", "Reviewer can answer"], [["Report", "Report ID and source hash", "Which source document was scored?"], ["Question", "Question ID, gold answer and generated answer", "Was this benchmark decision correct?"], ["Retrieval", "Returned IDs/scores and gold IDs", "Was relevant evidence available to the model?"], ["Generation", "Model, prompt, seed, temperature, raw/schema output", "Can the result be replayed?"], ["Audit", "Positive count, percentage, threshold, PASS/FAIL", "How did question outcomes become the final score?"]], [1550, 4200, 3960])),
        ("Harness review conclusion", ["The evaluation harness is the core control that turns an LLM answer into an auditable experiment. It produces machine-readable question-level CSV/JSON files, retrieval and answer metrics, faithfulness measures, audit scores, a run log and frozen configuration. [E4][E5]", "The 70% report-level threshold is a reproducible POC scoring rule, not an expert certification rule. The separate release gate remains BLOCKED, which correctly prevents two passing sample reports from being interpreted as production validation. [E5][E10]"]),
    ],
    "D10_Results_and_Error_Analysis": [
        ("Observed Qwen3 decision errors", ("table", ["Gold class", "Predicted Yes", "Predicted No", "Interpretation"], [["Yes (n=12)", "12", "0", "The run captured all source-derived positive labels."], ["No (n=4)", "3", "1", "Negative claims are the primary observed failure mode."], ["Insufficient Evidence (n=0)", "0", "0", "Abstention quality cannot be estimated from this set."]], [1850, 1900, 1900, 4160])),
        ("Error-analysis conclusion", ["The 81.25% headline accuracy must be read together with the confusion matrix. The model's 100% recall on Yes is encouraging for this POC, but No recall is only 25%; the system tends to convert absence/negative statements into a positive conclusion. Macro-F1 of 0.4296 captures this imbalance better than accuracy alone. [E5]", "The correct response is not to hide the failure in an aggregate score. The next dataset should deliberately include negative, contradiction and missing-evidence questions with independent labels, while retrieval and prompt changes are tested against that frozen set. [E10]"]),
    ],
    "D11_Integrated_Proof_of_Concept": [
        ("Observed report-level assessment", ("table", ["Report", "Questions", "Yes / No / Insufficient", "Score", "POC decision"], [["2-REPORT", "8", "8 / 0 / 0", "100.0%", "PASS at 70% threshold"], ["4-REPORT", "8", "7 / 1 / 0", "87.5%", "PASS at 70% threshold"], ["Production release", "2 reports", "12 Yes / 4 No / 0 IE labels", "Not applicable", "BLOCKED evidence gate"]], [1650, 1050, 2500, 1300, 3310])),
        ("POC acceptance conclusion", ["The complete POC has been demonstrated on two actual supplied report files, not synthetic generated reports. It produces an audit score from the eight benchmark questions for each report and retains the question-level evidence needed to inspect both PASS outcomes. [E4][E5]", "The production gate is intentionally more conservative than the POC scorer. A sample report can pass its selected benchmark while the system is still blocked from operational use because the evidence corpus lacks breadth, independent review and missing-evidence labels. That distinction is a strength of the submission, not a caveat hidden at the end. [E10]"]),
    ],
    "D12_Final_Technical_Report_and_Demo": [
        ("Final review claims and support", ("table", ["Final claim", "Supporting evidence", "Boundary"], [["A local RAG pipeline was implemented", "Parser, hybrid index, prompt, harness and 16-pair run. [E4][E8]", "Text/JSON scope; visual understanding unvalidated."], ["Architecture choices were tested", "LLM, ICL, prompt, retrieval, CRAG and chunking comparisons. [E10]", "Small source-derived dataset."], ["Scores are traceable", "Question records, metrics, audit scores, logs and config. [E4][E5]", "Gold labels are not independent expert labels."], ["The POC is technically credible", "Two reports completed with zero execution errors. [E4]", "Not a production readiness claim."]], [2350, 4270, 2840])),
        ("Submission conclusion", ["This final package demonstrates the complete requested workflow: audit report input, benchmark question, evidence retrieval, constrained local LLM response, positive/negative assessment, audit score and benchmark decision. Its central contribution is traceability: every claimed score has a route back to source report, retrieval evidence, configuration and answer record. [E4][E5]", "The final recommendation is to submit this as an evaluated, auditable proof of concept. State plainly in the review that broader deployment requires independently labelled multi-report validation, balanced answer classes and visual/OCR coverage where the input data demands it. [E10]"]),
    ],
}

EVIDENCE_BY_DOC = {
    "D01_Literature_and_Technology_Review": [0, 3, 7, 9],
    "D02_LLM_Selection_and_Justification": [2, 3, 4, 9],
    "D03_Zero_Shot_and_ICL_Design": [6, 7, 9],
    "D04_Preprocessing_Chunking_and_Retrieval": [3, 5, 6, 7, 9],
    "D05_Retrieval_Evaluation_and_Cases": [3, 4, 5, 9],
    "D06_Prompt_Design_and_Justification": [3, 6, 7, 9],
    "D07_Integrated_RAG_Chatbot_Prototype": [3, 4, 6, 7],
    "D08_Evaluation_Dataset_and_Methodology": [3, 4, 5, 9],
    "D09_Automated_Evaluation_Harness": [3, 4, 6, 9],
    "D10_Results_and_Error_Analysis": [3, 4, 9],
    "D11_Integrated_Proof_of_Concept": [3, 4, 5, 9],
    "D12_Final_Technical_Report_and_Demo": [3, 4, 7, 9],
}

DETAILED_REVIEW_NOTES = {
    "D03_Zero_Shot_and_ICL_Design": [
        ("Implementation and retest requirement", ["Three ICL strategies are implemented in icl.py. Zero shot returns no demonstrations; fixed few shot chooses a class-diverse local set; retrieval few shot embeds the local question bank and selects the nearest four examples for the incoming benchmark question. The prompt builder inserts demonstrations before the report evidence and clearly separates the two. [E8]", "That separation matters operationally. An example may teach the model how to answer a segmentation question, but it cannot prove that the target report has segmentation. The final verdict must always cite chunks retrieved from the target report, and the citation validator rejects IDs outside that returned context. [E7][E8]", "The next controlled run should repeat zero-shot and retrieval-few-shot settings with Qwen3-8B, hold retrieval/prompt/seed fixed, and add independent No and Insufficient Evidence cases. Only then can ICL be selected for the final Qwen3 configuration rather than inherited from the current implementation. [E10]"]),
    ],
    "D05_Retrieval_Evaluation_and_Cases": [
        ("Reviewer inspection protocol", ["For each benchmark question, the reviewer should inspect three records together: the source-derived gold chunk ID, the returned top-eight chunk IDs and scores, and the final answer/cited evidence. This distinguishes a retrieval failure from a generation failure. The run has both cases: RQ1 and RQ5 for 4-REPORT miss the labelled evidence, while the final score can still look strong. [E4][E5]", "The reported precision is deliberately low because one or a few gold chunks are compared with eight returned candidates. It should therefore not be read as eight irrelevant passages; it is a ranking diagnostic that shows how much non-gold context was passed to the model. The next practical improvement is reranking or reduced evidence packing, evaluated on independently labelled evidence spans. [E5][E8]", "The conclusion is appropriately cautious: retrieval is functional and measurable, not yet accurate enough to be invisible in the final decision. The submission preserves the exact failure cases so an evaluator can challenge the claimed score with primary output rather than accepting a summary metric. [E5]"]),
    ],
    "D08_Evaluation_Dataset_and_Methodology": [
        ("Label provenance and split policy", ["The current 16 records use the same eight benchmark-question templates across both supplied reports. This is useful for checking whether the integrated pipeline can apply a stable assessment rubric to more than one input, and the stored report/question IDs make every aggregate count reproducible. [E4][E6]", "It is not a train/test split. The questions and labels were authored from the supplied reports, so there is a risk that the benchmark reflects obvious report wording rather than the more difficult expert judgement required in deployment. This is why the package labels the work an evaluated POC instead of a validated decision system. [E10]", "The next dataset must be frozen before model comparison: separate reports by source at report level, have domain reviewers label the verdict and acceptable evidence spans, and reserve missing-evidence/contradiction cases. This prevents accidental leakage and permits credible per-class error reporting. [E8]"]),
    ],
    "D10_Results_and_Error_Analysis": [
        ("Prioritised remediation plan", ["Priority one is negative and absence-sensitive reasoning. The three false-positive No cases show that the generator needs evidence that positively establishes a universal claim such as all findings being closed; the absence of a contradiction must not become a Yes. This should be addressed through new labels, prompt tests and claim-level verification. [E5][E8]", "Priority two is retrieval ordering. With MRR 0.2781, the relevant evidence is often available but buried below competing content. Reranking should be tested as one isolated variable on a re-labelled evidence benchmark, rather than enabled as an unmeasured architecture embellishment. [E5][E10]", "Priority three is abstention. The schema supports Insufficient Evidence, but its safety cannot be measured until that class exists in the gold data. Completion of this data work is the release-gate requirement; it is not something an attractive accuracy score can substitute. [E10]"]),
    ],
    "D11_Integrated_Proof_of_Concept": [
        ("Demonstration sequence for review", ["A reviewer can reproduce the POC narrative in five steps: identify one supplied JSON report; select one of the eight benchmark questions; inspect the retrieved chunk IDs and source paths; inspect the schema response and its cited evidence; then verify how the harness adds the Yes outcomes into the report score. The saved result files preserve every one of these stages. [E4][E5]", "For 2-REPORT the harness records eight positive answers and therefore a 100% score. For 4-REPORT it records seven positive answers and one negative answer, producing 87.5%. Both clear the explicit 70% POC threshold. The figures are descriptive outcomes of the current rubric, not a statement that the reports are objectively secure. [E5]", "The final POC acceptance condition is thus satisfied: the requested workflow exists, runs locally and is auditable. The intentionally separate release decision remains BLOCKED until evidence quality, not merely implementation completeness, improves. [E10]"]),
    ],
}


def build_one(filename, spec):
    doc = Document()
    section = doc.sections[0]
    section.top_margin = section.bottom_margin = section.left_margin = section.right_margin = Inches(1)
    section.header_distance = section.footer_distance = Inches(0.492)
    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = BLACK
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15
    for name, size, before, after in (("Heading 1", 16, 15, 7), ("Heading 2", 13, 11, 5), ("Heading 3", 11, 8, 4)):
        style = styles[name]
        style.font.name = "Arial"
        style.font.size = Pt(size)
        style.font.color.rgb = BLACK
        style.font.bold = True
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.line_spacing = 1.1
    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_font(header.add_run("Objective 3 | AI-Based Cyber Security Audit Assessment Against Benchmark"), size=8.5)
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(footer.add_run(filename.replace("_", " ")), size=8.5)

    title = doc.add_paragraph()
    title.paragraph_format.space_after = Pt(3)
    set_font(title.add_run(spec["title"]), size=22, bold=True)
    sub = doc.add_paragraph()
    sub.paragraph_format.space_after = Pt(14)
    set_font(sub.add_run(spec["purpose"]), size=11, italic=True)
    meta = [("Project", "Development of AI-Based Cyber Security Audit Assessment Against Benchmark"), ("Scope", "Objective 3; secure local/air-gapped RAG proof of concept"), ("Report date", "28 August 2026"), ("Evidence rule", "Implemented, tested and untested claims are labelled separately.")]
    add_table(doc, ["Field", "Value"], meta, [1850, 7510])
    for heading, content in TAILORED_SECTIONS[filename]:
        doc.add_heading(heading, level=1)
        if isinstance(content, tuple) and content[0] == "table":
            _, headers, rows, widths = content
            add_table(doc, headers, rows, widths)
        else:
            for paragraph in content:
                add_para(doc, paragraph)

    for heading, content in spec["sections"]:
        doc.add_heading(heading, level=1)
        if isinstance(content, tuple) and content[0] == "table":
            _, headers, rows, widths = content
            add_table(doc, headers, rows, widths)
        else:
            for paragraph in content:
                add_para(doc, paragraph)
    for heading, content in FINAL_REVIEW_EXHIBITS[filename]:
        doc.add_heading(heading, level=1)
        if isinstance(content, tuple) and content[0] == "table":
            _, headers, rows, widths = content
            add_table(doc, headers, rows, widths)
        else:
            for paragraph in content:
                add_para(doc, paragraph)
    for heading, content in DETAILED_REVIEW_NOTES.get(filename, []):
        doc.add_heading(heading, level=1)
        for paragraph in content:
            add_para(doc, paragraph)
    if filename in SUPPLEMENTS:
        doc.add_heading("Engineering rationale and review use", level=1)
        for paragraph in SUPPLEMENTS[filename]:
            add_para(doc, paragraph)

    doc.add_heading("Repository evidence cited", level=1)
    add_bullets(doc, [EVIDENCE[i] for i in EVIDENCE_BY_DOC[filename]])
    if filename.startswith("D01") or filename.startswith("D02") or filename.startswith("D12"):
        doc.add_heading("External technology sources", level=1)
        add_bullets(doc, SOURCES)
    doc.save(OUT / f"{filename}.docx")


def pdf_styles():
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("ReportTitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=colors.black, spaceAfter=4),
        "subtitle": ParagraphStyle("Subtitle", parent=styles["Normal"], fontName="Helvetica-Oblique", fontSize=10.5, leading=13, textColor=colors.black, spaceAfter=12),
        "h1": ParagraphStyle("Section", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=colors.black, spaceBefore=13, spaceAfter=6),
        "body": ParagraphStyle("Body", parent=styles["Normal"], fontName="Helvetica", fontSize=9.7, leading=12.4, textColor=colors.black, spaceAfter=7),
        "cell": ParagraphStyle("Cell", parent=styles["Normal"], fontName="Helvetica", fontSize=7.4, leading=9.1, textColor=colors.black),
        "cell_head": ParagraphStyle("CellHead", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7.4, leading=9.1, textColor=colors.black),
        "bullet": ParagraphStyle("Bullet", parent=styles["Normal"], fontName="Helvetica", fontSize=8.8, leading=11, leftIndent=13, firstLineIndent=-9, textColor=colors.black, spaceAfter=3),
    }


def pdf_table(headers, rows, widths, styles):
    scale = 504 / sum(widths)
    col_widths = [w * scale for w in widths]
    data = [[Paragraph(escape(str(v)), styles["cell_head"]) for v in headers]]
    data += [[Paragraph(escape(str(v)), styles["cell"]) for v in row] for row in rows]
    table = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.45, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def pdf_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.drawString(54, 30, "Objective 3 | AI-Based Cyber Security Audit Assessment")
    canvas.drawRightString(558, 30, f"Page {doc.page}")
    canvas.setLineWidth(0.35)
    canvas.line(54, 42, 558, 42)
    canvas.restoreState()


def build_pdf(filename, spec):
    PDF_OUT.mkdir(parents=True, exist_ok=True)
    styles = pdf_styles()
    doc = SimpleDocTemplate(str(PDF_OUT / f"{filename}.pdf"), pagesize=letter, leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=58, title=spec["title"], author="Objective 3 project repository")
    story = [Paragraph(escape(spec["title"]), styles["title"]), Paragraph(escape(spec["purpose"]), styles["subtitle"])]
    story.append(pdf_table(["Field", "Value"], [
        ["Project", "Development of AI-Based Cyber Security Audit Assessment Against Benchmark"],
        ["Scope", "Objective 3; secure local/air-gapped RAG proof of concept"],
        ["Report date", "28 August 2026"],
        ["Evidence rule", "Implemented, tested and untested claims are labelled separately."],
    ], [1850, 7510], styles))
    for heading, content in TAILORED_SECTIONS[filename]:
        story.append(Paragraph(escape(heading), styles["h1"]))
        if isinstance(content, tuple) and content[0] == "table":
            _, headers, rows, widths = content
            story.append(pdf_table(headers, rows, widths, styles))
        else:
            story += [Paragraph(escape(paragraph), styles["body"]) for paragraph in content]
    for heading, content in spec["sections"]:
        story.append(Paragraph(escape(heading), styles["h1"]))
        if isinstance(content, tuple) and content[0] == "table":
            _, headers, rows, widths = content
            story.append(pdf_table(headers, rows, widths, styles))
        else:
            story += [Paragraph(escape(paragraph), styles["body"]) for paragraph in content]
    for heading, content in FINAL_REVIEW_EXHIBITS[filename]:
        story.append(Paragraph(escape(heading), styles["h1"]))
        if isinstance(content, tuple) and content[0] == "table":
            _, headers, rows, widths = content
            story.append(pdf_table(headers, rows, widths, styles))
        else:
            story += [Paragraph(escape(paragraph), styles["body"]) for paragraph in content]
    for heading, content in DETAILED_REVIEW_NOTES.get(filename, []):
        story.append(Paragraph(escape(heading), styles["h1"]))
        story += [Paragraph(escape(paragraph), styles["body"]) for paragraph in content]
    if filename in SUPPLEMENTS:
        story.append(Paragraph("Engineering rationale and review use", styles["h1"]))
        story += [Paragraph(escape(paragraph), styles["body"]) for paragraph in SUPPLEMENTS[filename]]
    story.append(Paragraph("Repository evidence cited", styles["h1"]))
    story += [Paragraph("- " + escape(EVIDENCE[i]), styles["bullet"]) for i in EVIDENCE_BY_DOC[filename]]
    if filename.startswith("D01") or filename.startswith("D02") or filename.startswith("D12"):
        story.append(Paragraph("External technology sources", styles["h1"]))
        story += [Paragraph("- " + escape(item), styles["bullet"]) for item in SOURCES]
    doc.build(story, onFirstPage=pdf_footer, onLaterPages=pdf_footer)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for filename, spec in DOCS.items():
        build_one(filename, spec)
        build_pdf(filename, spec)
    assert len(list(OUT.glob("D*.docx"))) == 12
    assert len(list(PDF_OUT.glob("D*.pdf"))) == 12
    print(f"Built 12 DOCX source files in {OUT} and 12 PDFs in {PDF_OUT}")


if __name__ == "__main__":
    main()
