import json
import requests
from rule_engine.matcher.prompt import build_prompt
from rule_engine.config import LLM_MODEL,LLM_BASE_URL

def llm_match(domain,schema_headings,report_headings,hints):
    prompt=build_prompt(domain,schema_headings,report_headings,hints)
    # print(prompt)
    try:
        response=requests.post(
            LLM_BASE_URL,
            json={
                "model":LLM_MODEL,
                "prompt":prompt,
                "stream":False,
                "format": "json",
                "options": { 
                    "temperature":0.0,
                    "num_predict": 512
                },
                
            },
            timeout=120
        )
        response.raise_for_status()
        raw = response.json().get("response", "")
        result = _parse_response(raw)
        return result
    except requests.exceptions.Timeout:
        raise RuntimeError("LLM request timed out.")
    except requests.exceptions.ConnectionError:
        raise RuntimeError("cannot connect to endpoint.")
    except Exception as e:
        raise RuntimeError(f"LLM call failed: {e}") from e
    
def _parse_response(raw:str):
    raw=raw.strip()
    if raw.startswith("```"):
        lines=raw.split("\n")
        raw="\n".join(lines[1,-1])
    try:
        parsed=json.loads(raw)
    except Exception as e:
        raise RuntimeError(f"invalid json from llm, error{e}")
    
    if "matches" not in parsed:
        parsed["matches"] = {}
    if "missing" not in parsed:
        parsed["missing"] = []
    if "extra" not in parsed:
        parsed["extra"] = []
    return parsed