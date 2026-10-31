# -*- coding: utf-8 -*-
"""Edge (on-machine small-model) inference provider (P6).

Runs the <=1B candidate models LOCALLY on CPU via HF transformers with weights
downloaded from ModelScope — Apple M4 (arm64) CPU, torch 2.14 / transformers
5.17. This is the honest "端侧" for this machine: no llama.cpp / no ollama
server is installed (ollama-local is down, binary absent), and no <=1B model
is listed on the reachable cloud endpoint (ollama-cloud catalog has none),
so edge = on-device transformers CPU inference. tok/s is counted with each
model's OWN tokenizer (真 tokenizer 口径), recorded per call.

Interface matches ConfiguredEndpointProvider: generate() -> str, plus
chat(messages) -> (text, usage_dict) for the agents layer.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from transcoder.providers import LLMProvider


class EdgeTransformersProvider(LLMProvider):
    """One local <=1B model, transformers CPU, honest per-call telemetry."""

    def __init__(self, model_path: str, model_tag: str, max_new_tokens: int = 512,
                 threads: Optional[int] = None, dtype: str = "float32",
                 default_temperature: float = 0.3):
        self.model_path = model_path
        self.model_tag = model_tag
        self.max_new_tokens = max_new_tokens
        self.threads = threads
        self.dtype = dtype
        self.default_temperature = default_temperature
        self._tok = None
        self._model = None
        self.load_secs: Optional[float] = None
        self.gen_log: List[dict] = []  # (tag, prompt_tokens, completion_tokens, secs, tok_s)

    # -- loading ----------------------------------------------------------- #

    def _load(self):
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if self.threads:
            torch.set_num_threads(self.threads)
        t0 = time.time()
        self._tok = AutoTokenizer.from_pretrained(self.model_path)
        try:
            self._model = AutoModelForCausalLM.from_pretrained(
                self.model_path, dtype=self.dtype, device_map="cpu")
        except TypeError:  # torch_dtype naming differences across versions
            self._model = AutoModelForCausalLM.from_pretrained(self.model_path, device_map="cpu")
        self._model.eval()
        self.load_secs = round(time.time() - t0, 1)

    def tokenizer(self):
        self._load()
        return self._tok

    # -- LLMProvider API ---------------------------------------------------- #

    def chat(self, messages: List[dict], model: Optional[str] = None, temperature: Optional[float] = None,
             max_new_tokens: Optional[int] = None, seed: Optional[int] = None):
        """Chat-style generation. Returns (text, usage_dict). Seed-fixed for reproducibility."""
        import torch

        self._load()
        temperature = self.default_temperature if temperature is None else temperature
        if seed is not None:
            torch.manual_seed(int(seed))
        try:  # Qwen3-style templates support disabling thinking mode
            prompt = self._tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                                   enable_thinking=False)
        except Exception:
            prompt = self._tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self._tok(prompt, return_tensors="pt")
        prompt_tokens = int(inputs["input_ids"].shape[1])
        t0 = time.time()
        gen_kwargs = dict(max_new_tokens=max_new_tokens or self.max_new_tokens, do_sample=temperature > 0,
                          temperature=float(temperature))
        try:
            with torch.no_grad():
                out_ids = self._model.generate(**inputs, **gen_kwargs)
        except Exception as e:
            # Fallback: greedy without sampling args (some tiny models restrict sampling)
            with torch.no_grad():
                out_ids = self._model.generate(
                    **inputs, max_new_tokens=max_new_tokens or self.max_new_tokens, do_sample=False)
        gen_len = int(out_ids.shape[1]) - prompt_tokens
        secs = time.time() - t0
        text = self._tok.decode(out_ids[0][prompt_tokens:], skip_special_tokens=True).strip()
        record = {
            "tag": self.model_tag, "prompt_tokens": prompt_tokens, "completion_tokens": gen_len,
            "secs": round(secs, 2), "tok_s": round(gen_len / secs, 2) if secs > 0 else None,
        }
        self.gen_log.append(record)
        usage = {"prompt_tokens": prompt_tokens, "completion_tokens": gen_len,
                 "tok_s": record["tok_s"], "secs": record["secs"]}
        return text, usage

    def generate(self, prompt: str, model: Optional[str] = None, temperature: Optional[float] = None,
                 max_new_tokens: Optional[int] = None, seed: Optional[int] = None) -> str:
        text, _ = self.chat([{"role": "user", "content": prompt}], model=model,
                            temperature=temperature, max_new_tokens=max_new_tokens, seed=seed)
        return text

    def get_available_models(self) -> List[str]:
        return [self.model_tag]

    def is_available(self) -> bool:
        try:
            self._load()
            return self._model is not None
        except Exception:
            return False