# D2 - Candidate LLM comparison and selection

## Criteria

Accuracy, macro-F1 with an actual abstention class, claim-level evidence support, instruction following, JSON reliability, latency, RAM/VRAM, offline packaging, license, checksum verification and human-review compatibility.

## Candidates

| Candidate | Role | Decision |
|---|---|---|
| Qwen2.5 7B | Existing generator | B0 baseline; observed live run |
| Qwen3 8B | Local generator | Tested successfully through Ollama; slower due to CPU/GPU offload |
| Qwen3 14B | Higher-quality generator | Test if hardware permits |
| Llama 3.x 8B | Comparison generator | Test under identical prompts and context |

The current selection remains Qwen2.5 7B as the reproducible baseline until a larger labelled benchmark is available. The RTX 4050 Qwen3-0.6B run scored 58.33% accuracy and predicted No for all questions; it is not selected. Qwen3-8B ran successfully through Ollama, but its audit score was 33.33% (FAIL) after roughly 22 minutes for 12 questions, so it is a viable laptop deployment candidate but not evidence of production superiority.
