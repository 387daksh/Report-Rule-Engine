import json
from rule_engine.config import MAIN_HEADING_WEIGHT,SUB_HEADING_WEIGHT,COMPLIANT_THRESHOLD,PARTIAL_THRESHOLD

def score(schema,matches,missing):
    earned=0
    total=0
    for item in schema:
        heading=item["heading"]
        weight = MAIN_HEADING_WEIGHT if item["type"] == "main" else SUB_HEADING_WEIGHT
        total += weight
        if heading in matches:
            earned += weight
    compliance_score = round((earned / total) * 100, 2) if total > 0 else 0.0
    if compliance_score >= COMPLIANT_THRESHOLD:
        status = "COMPLIANT"
    elif compliance_score >= PARTIAL_THRESHOLD:
        status = "PARTIALLY_COMPLIANT"
    else:
        status = "NON_COMPLIANT"
    return {
        "compliance_score": compliance_score,
        "status": status,
        "earned_points": earned,
        "total_points": total,
        "matched_count": len(matches),
        "missing_count": len(missing)
    }    