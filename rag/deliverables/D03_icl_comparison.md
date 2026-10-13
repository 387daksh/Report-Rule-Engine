# D3 - Zero-shot and ICL comparison

Implemented strategies are `zero_shot`, `fixed_few_shot`, and `retrieval_few_shot` in `src/icl.py`. The default uses four semantically selected demonstrations from `sample_data/icl_example_bank.json`.

The comparison must hold the report, questions, retrieval context, generator, temperature and seed constant while changing only ICL strategy and k. Report answer accuracy, macro-F1, abstention safety, grounding and latency. The existing saved run used retrieval few-shot with k=4; a complete live ablation matrix is still required before claiming that it is optimal.
