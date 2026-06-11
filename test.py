from rule_engine import validate_report

result = validate_report(
    domain="network",
    headings=[
        "Project Background",                    # Introduction
        "Assessment Perimeter",                  # Engagement Scope - not in regex
        "Security Team Composition",             # Details of Auditing Team - not in regex
        "Testing Schedule",                      # Audit Activities and Timelines - not in regex
        "Testing Standards and Approach",        # Audit Methodology - not in regex
        "Security Tools Deployed",               # Tools/Software Used - not in regex
        "High Level Findings Overview",          # Executive Summary - not in regex
        "Vulnerability Deep Dive",               # Detailed Observations - not in regex
        "Supporting Documentation",              # Appendices - not in regex
        "Risk Scoring Framework",                # Risk Assessment Matrix - not in regex
        "Threat Classification Table",           # Risk Rating Criteria - not in regex
        "Severity Rating"
    ]
)

import json
print(json.dumps(result, indent=2))
