import re

def _normalise(text: str)-> str:
    text=text.lower()
    text = re.sub(r"[-_]", " ", text)
    text=re.sub(r"[^a-z0-9\s]","",text)
    text=re.sub(r"[\s+]"," ",text).strip()
    return text
def get_exact_hints(schema_headings:list[str],report_headings:list[str])->list[dict]:
    hints=[]
    norm_report={_normalise(h):h for h in report_headings}
    for sh in schema_headings:
        norm_sh=_normalise(sh)
        if norm_sh in norm_report:
            hints.append({
                "schema_heading":sh,
                "report_heading":norm_report[norm_sh],
                "method":"exact"
            })
    return hints
    