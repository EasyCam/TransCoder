"""Fast semantic scoring for a translation (no LLM call).

SOTA-ish and cheap: multilingual sentence embeddings
(paraphrase-multilingual-MiniLM-L12-v2) give a cross-lingual semantic
similarity between source and translation; when a reference translation is
available, its similarity and chrF are folded in. Everything runs locally in
tens of milliseconds after the model is loaded once.

Score mapping (heuristic, documented for honesty): cosine in [0.2, 1.0] is
stretched to 0-10. It is a fast triage signal, not a calibrated psychometric
scale; use the LLM rubric for detailed feedback.
"""

import threading
import time
from typing import Any, Dict, List, Optional

_EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class SemanticScorer:
    def __init__(self, model_name: str = _EMBED_MODEL, model=None):
        self.model_name = model_name
        self._model = model
        self._lock = threading.Lock()

    def _ensure_model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer

                    self._model = SentenceTransformer(self.model_name, device="cpu")
        return self._model

    def embed(self, texts: List[str]):
        model = self._ensure_model()
        return model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)

    @staticmethod
    def _to_10(cos: float) -> float:
        return round(max(0.0, min(10.0, (cos - 0.2) / 0.8 * 10.0)), 1)

    def score(self, source_text: str, translation: str, reference: Optional[str] = None) -> Dict[str, Any]:
        start = time.time()
        source_text = (source_text or "").strip()
        translation = (translation or "").strip()
        reference = (reference or "").strip() or None
        if not source_text or not translation:
            return {"error": "source_text and translation are required", "latency_ms": 0}

        texts = [source_text, translation] + ([reference] if reference else [])
        emb = self.embed(texts)
        cos_src = float(emb[0] @ emb[1])
        out: Dict[str, Any] = {
            "semantic_similarity": round(cos_src, 4),
            "semantic_score": self._to_10(cos_src),
            "latency_ms": 0,
        }

        if reference:
            cos_ref = float(emb[1] @ emb[2])
            chrf = None
            try:
                from sacrebleu.metrics import CHRF

                chrf = round(CHRF().corpus_score([translation], [[reference]]).score, 2)
            except Exception:
                chrf = None
            out.update({
                "reference_similarity": round(cos_ref, 4),
                "reference_score": self._to_10(cos_ref),
                "chrf": chrf,
            })
            out["combined_score"] = round(0.5 * out["semantic_score"] + 0.5 * out["reference_score"], 1)

        out["latency_ms"] = int((time.time() - start) * 1000)
        return out


_SCORER: Optional[SemanticScorer] = None


def get_scorer() -> SemanticScorer:
    global _SCORER
    if _SCORER is None:
        _SCORER = SemanticScorer()
    return _SCORER
