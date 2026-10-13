# D11 - Final integrated proof of concept

The demonstration now includes the two supplied real JSON reports. The production-shaped run parsed both reports into 22 finding-preserving chunks, applied PII redaction, used CUDA-safe Qwen3 embeddings, hybrid retrieval, parent-child and graph evidence, CRAG, prompt-injection detection, and Qwen3-8B generation through Ollama. It completed 16 report-question pairs with 81.25% accuracy, 100% grounding, 87.50% Recall@8, and 13.66 seconds mean latency. The reranker and claim verifier were disabled in this 6 GB laptop run to keep the generator GPU-resident; this is documented as a hardware tradeoff, not a missing implementation.

Run from `rag/src`:

```text
python test_harness_mock.py
```

The live saved run is under `src/results/1787426063_6d47ba9f8ee0/`. It is evidence of a working proof of concept, not a production validation study.
