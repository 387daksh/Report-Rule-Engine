import json
import os
from rule_engine.config import SUPPORTED_DOMAINS
from rule_engine.hints import get_exact_hints, get_regex_hints, get_embedding_hints
from rule_engine.matcher import llm_match
from rule_engine.scorer import score
from rule_engine.reporter import build_report


def _load_schema(domain):
    schema_path = os.path.join(os.path.dirname(__file__), "schemas", f"{domain}.json")
    with open(schema_path, "r") as f:
        data = json.load(f)
    return data["headings"]


def validate_report(domain, headings):
    if domain not in SUPPORTED_DOMAINS:
        raise ValueError(f"Unsupported domain: '{domain}'. Must be one of {SUPPORTED_DOMAINS}")

    if not headings:
        raise ValueError("Headings list is empty.")

    # load schema
    schema = _load_schema(domain)
    schema_headings = [item["heading"] for item in schema]

    # generate hints
    exact_hints = get_exact_hints(schema_headings, headings)
    regex_hints = get_regex_hints(domain, schema_headings, headings)
    embedding_hints=get_embedding_hints(schema_headings,headings)

    # merge hints
    seen = set()
    hints = []
    for hint in exact_hints + regex_hints + embedding_hints:
        if hint["schema_heading"] not in seen:
            hints.append(hint)
            seen.add(hint["schema_heading"])
    # print("EXACT HINTS:", exact_hints)
    # print("REGEX HINTS:", regex_hints)
    # print("EMBEDDING HINTS:", embedding_hints)
    # print("MERGED HINTS:", hints)

    # LLM
    llm_result = llm_match(domain, schema_headings, headings, hints)

    matches = llm_result["matches"]
    missing = llm_result["missing"]
    extra = llm_result["extra"]

    # score
    score_result = score(schema, matches, missing)

    #final report
    report = build_report(domain, schema, matches, missing, extra, hints, score_result)

    return report