# D6 - Final chatbot prompt design

`src/prompts.py` provides `v1_direct` and `v2_evidence_review`. The selected prompt is v2: it requires a single JSON object, an answer from Yes/No/Insufficient Evidence, supporting evidence, cited chunk IDs and a justification. It instructs the model to silently verify each chunk before responding.

The schema now also permits `claim_evidence` and `abstention_reason`, allowing future claim-level verification without breaking the existing required fields. Prompt-injection text inside source documents must be treated as untrusted evidence, never as an instruction.
