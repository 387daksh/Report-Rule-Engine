def build_prompt(domain, schema_headings, report_headings, hints):

    schema_list = "\n".join(f"  - {h}" for h in schema_headings)
    report_list = "\n".join(f"  - {h}" for h in report_headings)

    hint_lines = ""
    if hints:
        hint_lines = "\nPattern analysis has detected these possible matches (not confirmed, use as hints only):\n"
        for hint in hints:
            if hint["method"] == "embedding":
                hint_lines += f"  - \"{hint['schema_heading']}\" → \"{hint['report_heading']}\" (embedding similarity: {hint.get('similarity', '')})\n"
            else:
                hint_lines += f"  - \"{hint['schema_heading']}\" → \"{hint['report_heading']}\" (detected by: {hint['method']})\n"
        hint_lines += """
High similarity score (>0.85) = very likely correct match.
Low similarity score (<0.70) = possible match, verify carefully.
Only override a high-confidence hint if you have a strong reason.
"""

    prompt = f"""You are an expert cybersecurity audit document reviewer specializing in MeitY (Ministry of Electronics and Information Technology) audit report standards.

You are given two lists:
1. Schema Headings — the required headings for a {domain.upper()} security audit report as per MeitY standards
2. Report Headings — the actual headings extracted from a submitted audit report

Your task:
- Map each schema heading to the most semantically equivalent report heading
- Each report heading can only be used once (strict one-to-one mapping) — never assign the same report heading to two different schema headings
- A match is valid even if the wording is different, as long as the meaning is the same
- If no reasonable match exists for a schema heading, mark it as missing
- Do not force a match if none exists

Schema Headings (required):
{schema_list}

Report Headings (extracted from submitted report):
{report_list}
{hint_lines}
Return ONLY a valid JSON object in this exact format with no explanation, no markdown, no extra text:
{{
  "matches": {{
    "Schema Heading": "Report Heading"
  }},
  "missing": ["Schema Heading"],
  "extra": ["Report Heading"]
}}

"extra" should contain all report headings that were not matched to any schema heading."""

    return prompt