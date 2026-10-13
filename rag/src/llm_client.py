"""
llm_client.py
-------------
SOTA Ollama client with token-level JSON Schema enforcement (/api/chat and /api/generate).

Offline discipline (Sec. 6.5): Ollama serves model weights from the local host
over http://localhost:11434 with zero external telemetry or cloud leakage.

Supported local models:
  - qwen3:8b / qwen3:14b / qwen3:32b
  - llama3.1:8b / llama3.3:70b
  - mistral:7b
  - phi4:14b
  - deepseek-r1:8b / deepseek-r1:14b

Features:
  - Native JSON Schema enforcement via `format` parameter (guaranteed valid JSON)
  - `/api/chat` multi-turn & system role support
  - Deterministic sampling (temperature=0.0, fixed seed) for compliance verification
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger("audit_rag.llm_client")

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"

AUDIT_ASSESSMENT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {
            "type": "string",
            "enum": ["Yes", "No", "Insufficient Evidence"],
        },
        "supporting_evidence": {
            "type": "string",
        },
        "evidence_chunk_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
        "justification": {
            "type": "string",
        },
        "claim_evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "chunk_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["claim", "chunk_ids"],
            },
        },
        "abstention_reason": {"type": "string"},
    },
    "required": ["answer", "supporting_evidence", "evidence_chunk_ids", "justification"],
}

CRAG_EVALUATION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {
            "type": "string",
            "enum": ["CORRECT", "AMBIGUOUS", "INCORRECT"],
        },
        "reasoning": {
            "type": "string",
        },
        "missing_information": {
            "type": "string",
        },
    },
    "required": ["verdict", "reasoning"],
}

CLAIM_VERIFICATION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "supported": {"type": "boolean"},
        "contradiction": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["supported", "contradiction", "reason"],
}


@dataclass
class GenerationConfig:
    model_name: str = "qwen3:8b"
    temperature: float = 0.0
    seed: int = 42
    num_predict: int = 512
    top_p: float = 1.0
    think: bool = False
    use_chat_api: bool = True
    enforce_schema: bool = True
    backend: str = "ollama"
    model_path: Optional[str] = None


class OllamaClient:
    def __init__(self, config: Optional[GenerationConfig] = None, max_retries: int = 3):
        self.config = config or GenerationConfig()
        self.max_retries = max_retries

    def chat(
        self,
        messages: List[Dict[str, str]],
        format_schema: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """Calls /api/chat with optional schema enforcement."""
        schema = format_schema if (format_schema is not None) else (AUDIT_ASSESSMENT_SCHEMA if self.config.enforce_schema else None)

        payload: Dict[str, Any] = {
            "model": self.config.model_name,
            "messages": messages,
            "stream": False,
            "think": self.config.think,
            "options": {
                "temperature": self.config.temperature,
                "seed": self.config.seed,
                "num_predict": self.config.num_predict,
                "top_p": self.config.top_p,
            },
        }
        if schema:
            payload["format"] = schema

        last_err = None
        for attempt in range(self.max_retries):
            t0 = time.time()
            try:
                resp = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=120)
                resp.raise_for_status()
                data = resp.json()
                latency = time.time() - t0
                content = data.get("message", {}).get("content", "").strip()
                return {
                    "text": content,
                    "latency_s": latency,
                    "model": self.config.model_name,
                    "raw": data,
                }
            except Exception as e:
                last_err = e
                logger.warning("Ollama /api/chat attempt %d failed: %s", attempt + 1, e)
                time.sleep(1.5 * (attempt + 1))

        # Fallback to generate endpoint if chat failed
        logger.info("Falling back from /api/chat to /api/generate for model %s", self.config.model_name)
        prompt_text = "\n\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)
        return self.generate(prompt_text, format_schema=format_schema)

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        format_schema: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """Calls /api/generate with optional schema enforcement."""
        schema = format_schema if (format_schema is not None) else (AUDIT_ASSESSMENT_SCHEMA if self.config.enforce_schema else None)

        payload: Dict[str, Any] = {
            "model": self.config.model_name,
            "prompt": prompt,
            "system": system or "",
            "stream": False,
            "think": self.config.think,
            "options": {
                "temperature": self.config.temperature,
                "seed": self.config.seed,
                "num_predict": self.config.num_predict,
                "top_p": self.config.top_p,
            },
        }
        if schema:
            payload["format"] = schema

        last_err = None
        for attempt in range(self.max_retries):
            t0 = time.time()
            try:
                resp = requests.post(OLLAMA_GENERATE_URL, json=payload, timeout=120)
                resp.raise_for_status()
                data = resp.json()
                latency = time.time() - t0
                return {
                    "text": data.get("response", "").strip(),
                    "latency_s": latency,
                    "model": self.config.model_name,
                    "raw": data,
                }
            except Exception as e:
                last_err = e
                logger.warning("Ollama /api/generate attempt %d failed: %s", attempt + 1, e)
                time.sleep(1.5 * (attempt + 1))

        raise RuntimeError(
            f"Ollama generation failed after {self.max_retries} attempts "
            f"(is `ollama serve` running and is model '{self.config.model_name}' pulled?). Last error: {last_err}"
        )


class LocalTransformersClient:
    """Offline Hugging Face generator; loads only from a local model path."""

    def __init__(self, config: Optional[GenerationConfig] = None):
        self.config = config or GenerationConfig()
        if not self.config.model_path:
            raise ValueError("generation.model_path is required for backend=transformers")
        from pathlib import Path
        if not Path(self.config.model_path).exists():
            raise FileNotFoundError(f"Local generator weights not found: {self.config.model_path}")
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch
        self.tokenizer = AutoTokenizer.from_pretrained(self.config.model_path, local_files_only=True)
        self.model = AutoModelForCausalLM.from_pretrained(self.config.model_path, local_files_only=True, torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self.device).eval()

    def _prompt(self, messages):
        if hasattr(self.tokenizer, "apply_chat_template"):
            return self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=self.config.think)
        return "\n\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages) + "\n\nASSISTANT:"

    def chat(self, messages: List[Dict[str, str]], format_schema=None):
        return self.generate(self._prompt(messages), format_schema=format_schema)

    def generate(self, prompt: str, system: Optional[str] = None, format_schema=None):
        import time
        import torch
        if system:
            prompt = f"SYSTEM: {system}\n\n{prompt}\n\nASSISTANT:"
        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=8192).to(self.device)
        t0 = time.time()
        with torch.inference_mode():
            output = self.model.generate(**inputs, max_new_tokens=self.config.num_predict, do_sample=self.config.temperature > 0, temperature=max(self.config.temperature, 1e-5), top_p=self.config.top_p, pad_token_id=self.tokenizer.eos_token_id)
        text = self.tokenizer.decode(output[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
        return {"text": text, "latency_s": time.time() - t0, "model": self.config.model_path, "raw": {}}
