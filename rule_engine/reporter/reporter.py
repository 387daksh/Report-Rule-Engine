def build_report(domain,schema,matches,missing,extra,hints,score_result):
    hint_lookup = {h["schema_heading"]: h["method"] for h in hints}
    breakdown = []
    for item in schema:
        heading = item["heading"]
        heading_type = item["type"]
 
        if heading in matches:
            method = hint_lookup.get(heading, "llm")
            breakdown.append({
                "schema_heading": heading,
                "matched_to": matches[heading],
                "type": heading_type,
                "status": "matched",
                "method": method,
                "points_earned": 5 if heading_type == "main" else 1
            })
        else:
            breakdown.append({
                "schema_heading": heading,
                "matched_to": None,
                "type": heading_type,
                "status": "missing",
                "method": None,
                "points_earned": 0
            })
    human_readable = []
    for item in breakdown:
        if item["status"] == "matched":
            if item["matched_to"] == item["schema_heading"]:
                human_readable.append(f"+ {item['schema_heading']} — Found (method: {item['method']})" )
            else:
                human_readable.append(f"+ {item['schema_heading']} — Found as \"{item['matched_to']}\" (method: {item['method']})")
        else:
            human_readable.append(f"- {item['schema_heading']} — Missing")
 
    for rh in extra:
        human_readable.append(f"? {rh} — Extra (not in schema)")        
    return {
        "domain": domain,
        "compliance_score": score_result["compliance_score"],
        "status": score_result["status"],
        "earned_points": score_result["earned_points"],
        "total_points": score_result["total_points"],
        "matched_count": score_result["matched_count"],
        "missing_count": score_result["missing_count"],
        "extra_count": len(extra),
        "breakdown": breakdown,
        "missing": missing,
        "extra": extra,
        "human_readable": human_readable
    }    