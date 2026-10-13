# D7 - Integrated RAG chatbot prototype

Entry point: `src/pipeline.py`, class `AuditAssessmentPipeline`.

Input: report ID, question ID and benchmark question. Output: retrieved IDs/scores, raw and parsed model response, supporting evidence, answer, CRAG decision, route, grounding state, review flags and configuration metadata.

The prototype is local-first and uses Ollama. It does not send audit data to a cloud API. `src/test_harness_mock.py` provides a no-download end-to-end demonstration.
