import re
import importlib

def get_regex_hints(domain: str, schema_headings:list[str],report_headings:list[str])->list[dict]:
    try:
        patterns_module=importlib.import_module(f"rule_engine.hints.patterns.{domain}") 
    except ModuleNotFoundError:
        print("domain modules not found")
        return []
    hints=[]
    for sh in schema_headings:
        for rh in report_headings:
            if patterns_module.match(sh,rh):
                hints.append({
                    "schema_heading":sh,
                    "report_heading":rh,
                    "method":"regex"
                })
                break
    return hints