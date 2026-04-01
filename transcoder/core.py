"""
TransCoder Core Module

Core services for translation, vector database, terminology, and evaluation.
"""

import json
import os
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import numpy as np

if TYPE_CHECKING:
    from transcoder.providers import LLMProvider

try:
    from langdetect import detect
except ImportError:
    detect = None

try:
    import faiss
    from sentence_transformers import SentenceTransformer
except ImportError:
    faiss = None
    SentenceTransformer = None


@dataclass
class ToolResult:
    """Unified result type for all API operations."""

    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
        }


class TranslationService:
    """Translation service with reflection-based improvement."""

    SUPPORTED_LANGUAGES = {
        "zh-cn": "中文大陆地区现代文简体",
        "zh-tw": "中文港澳台地区现代文繁体",
        "zh-classical-cn": "中文文言文简体",
        "zh-classical-tw": "中文文言文繁体",
        "en": "English",
        "ja": "日本語",
        "ko": "한국어",
        "es": "Español",
        "fr": "Français",
        "de": "Deutsch",
        "ru": "Русский",
        "ar": "العربية",
        "pt": "Português",
    }

    def __init__(
        self,
        model: str = "qwen3:0.6b",
        ollama_host: str = "http://localhost:11434",
        provider: Optional["LLMProvider"] = None,
        provider_type: str = "ollama",
        use_proxy: bool = False,
        proxy_url: Optional[str] = None,
    ):
        """
        Initialize translation service.

        Args:
            model: Default model name
            ollama_host: Ollama server host (deprecated, use provider_type)
            provider: LLMProvider instance (if provided, overrides other settings)
            provider_type: "ollama" or "openai"
            use_proxy: Whether to use proxy for API calls
            proxy_url: Proxy URL (e.g., socks5://127.0.0.1:7897)
        """
        self.model = model
        self.ollama_host = ollama_host

        if provider is not None:
            self._provider = provider
        else:
            from transcoder.providers import create_provider

            self._provider = create_provider(
                provider_type=provider_type, model=model, host=ollama_host, use_proxy=use_proxy, proxy_url=proxy_url
            )

    @property
    def provider(self) -> "LLMProvider":
        """Get the LLM provider."""
        return self._provider

    def get_available_models(self) -> List[str]:
        """Get list of available models."""
        return self._provider.get_available_models()

    def detect_language(self, text: str) -> str:
        """Detect language of text."""
        if detect is None:
            return "auto"
        try:
            lang = detect(text)
            return self._normalize_lang_code(lang)
        except Exception:
            return "auto"

    def _normalize_lang_code(self, lang: str) -> str:
        """Normalize language code."""
        lang_map = {
            "zh": "zh-cn",
            "zh-cn": "zh-cn",
            "zh-hans": "zh-cn",
            "zh-tw": "zh-tw",
            "zh-hant": "zh-tw",
            "en": "en",
            "ja": "ja",
            "ko": "ko",
            "es": "es",
            "fr": "fr",
            "de": "de",
            "ru": "ru",
            "ar": "ar",
            "pt": "pt",
        }
        return lang_map.get(lang.lower(), lang.lower()[:2] if len(lang) >= 2 else lang)

    def translate_single(
        self, source_text: str, source_lang: str, target_lang: str, model: Optional[str] = None
    ) -> ToolResult:
        """Translate text to a single target language."""
        start_time = time.time()

        try:
            model = model or self.model
            prompt = self._build_translation_prompt(source_text, source_lang, target_lang)

            translation = self._provider.generate(prompt, model=model)
            translation = self._clean_translation(translation)

            elapsed = time.time() - start_time
            word_count = len(translation.split())
            tokens_per_second = word_count / elapsed if elapsed > 0 else 0

            return ToolResult(
                success=True,
                data={
                    "text": translation,
                    "source_lang": source_lang,
                    "target_lang": target_lang,
                    "model": model,
                },
                metadata={
                    "elapsed_time": round(elapsed, 2),
                    "word_count": word_count,
                    "tokens_per_second": round(tokens_per_second, 1),
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def translate(
        self,
        source_text: str,
        source_lang: str,
        target_langs: List[str],
        model: Optional[str] = None,
        use_vector_db: bool = False,
        use_terminology: bool = False,
        vector_db_service: Optional["VectorDBService"] = None,
        terminology_service: Optional["TerminologyService"] = None,
    ) -> ToolResult:
        """Translate text to multiple target languages."""
        results = {}

        if source_lang == "auto":
            source_lang = self.detect_language(source_text)

        for target_lang in target_langs:
            result = self.translate_single(source_text, source_lang, target_lang, model)
            if result.success:
                results[target_lang] = result.data
            else:
                results[target_lang] = {"error": result.error}

        return ToolResult(success=True, data={"translations": results, "source_lang": source_lang})

    def translate_with_reflection(
        self, source_text: str, source_lang: str, target_lang: str, model: Optional[str] = None, iterations: int = 1
    ) -> ToolResult:
        """
        Translate with reflection-based improvement (三省吾身模式).

        This is the core innovation: AI self-reflection and improvement.
        - Initial translation -> Reflection -> Improved translation
        - Can iterate multiple times for better quality
        """
        model = model or self.model

        # Step 1: Initial translation
        initial_result = self.translate_single(source_text, source_lang, target_lang, model)
        if not initial_result.success:
            return initial_result

        current_translation = initial_result.data["text"]
        reflection_history = []

        for i in range(iterations):
            # Step 2: Reflect on translation
            reflection_result = self.reflect_translation(
                source_text, current_translation, source_lang, target_lang, model
            )
            if not reflection_result.success:
                break

            reflection = reflection_result.data["reflection"]

            # Step 3: Improve translation based on reflection
            improve_result = self.improve_translation(
                source_text, current_translation, reflection, source_lang, target_lang, model
            )
            if not improve_result.success:
                break

            improved = improve_result.data["improved_translation"]
            reflection_history.append(
                {
                    "iteration": i + 1,
                    "previous_translation": current_translation,
                    "reflection": reflection,
                    "improved_translation": improved,
                }
            )
            current_translation = improved

        return ToolResult(
            success=True,
            data={
                "text": current_translation,
                "source_lang": source_lang,
                "target_lang": target_lang,
                "model": model,
                "reflection_history": reflection_history,
                "iterations": len(reflection_history),
            },
        )

    def reflect_translation(
        self, source_text: str, translation: str, source_lang: str, target_lang: str, model: Optional[str] = None
    ) -> ToolResult:
        """
        AI reflects on translation quality (反思翻译).

        The AI analyzes:
        1. Accuracy - Is the meaning preserved?
        2. Fluency - Is the expression natural?
        3. Style - Is the tone appropriate?
        4. Terminology - Are terms translated correctly?
        """
        model = model or self.model

        prompt = f"""你是一位专业的翻译质量评审专家。请对以下翻译进行深入分析和反思。

原文({source_lang}):
{source_text}

译文({target_lang}):
{translation}

请从以下维度分析翻译质量：
1. 准确性：意思是否完整准确地传达
2. 流畅性：表达是否自然地道
3. 风格：语气和风格是否恰当
4. 术语：专业术语翻译是否准确

请指出翻译中的问题，并提出具体的改进建议。直接输出分析和建议，不要包含其他内容。"""

        try:
            reflection = self._provider.generate(prompt, model=model)

            return ToolResult(success=True, data={"reflection": reflection}, metadata={"model": model})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def improve_translation(
        self,
        source_text: str,
        current_translation: str,
        reflection: str,
        source_lang: str,
        target_lang: str,
        model: Optional[str] = None,
    ) -> ToolResult:
        """
        Improve translation based on reflection (改进翻译).

        Key innovation: Uses AI's own analysis to guide improvement,
        creating a self-improving translation loop.
        """
        model = model or self.model

        prompt = f"""你是一位专业翻译专家。请根据以下分析和建议，改进翻译。

原文({source_lang}):
{source_text}

当前译文({target_lang}):
{current_translation}

分析建议:
{reflection}

请输出改进后的翻译。只输出改进后的译文，不要包含任何解释或其他内容。"""

        try:
            improved = self._provider.generate(prompt, model=model)
            improved = self._clean_translation(improved)

            return ToolResult(success=True, data={"improved_translation": improved}, metadata={"model": model})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def translate_iterative(
        self, source_text: str, source_lang: str, target_lang: str, model: Optional[str] = None, iterations: int = 3
    ) -> ToolResult:
        """
        Iterative refinement translation (千锤百炼模式).

        This is the signature feature: configurable multi-round reflection
        and improvement, allowing users to balance quality vs speed.

        Args:
            iterations: Number of improvement iterations (1-10)

        Returns:
            ToolResult with translation and full improvement history
        """
        return self.translate_with_reflection(source_text, source_lang, target_lang, model, iterations)

    def _build_translation_prompt(self, text: str, source_lang: str, target_lang: str) -> str:
        """Build translation prompt."""
        lang_names = self.SUPPORTED_LANGUAGES
        source_name = lang_names.get(source_lang, source_lang)
        target_name = lang_names.get(target_lang, target_lang)

        return f"""请将以下{source_name}文本翻译成{target_name}。

原文:
{text}

请直接输出翻译结果，不要包含任何解释或其他内容。"""

    def _clean_translation(self, text: str) -> str:
        """Clean translation output."""
        text = text.strip()

        patterns = [
            ("以下是翻译", ""),
            ("翻译结果：", ""),
            ("译文：", ""),
            ("Translation:", ""),
            ("翻译：", ""),
        ]

        for pattern, replacement in patterns:
            if text.startswith(pattern):
                text = text[len(pattern) :].strip()

        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        if text.startswith("'") and text.endswith("'"):
            text = text[1:-1]

        return text


class VectorDBService:
    """Vector database for translation memory using FAISS."""

    def __init__(self, db_path: str = "data/vector_db", embedding_model: str = None):
        if SentenceTransformer is None:
            raise ImportError("sentence-transformers is required for VectorDBService")

        self.db_path = db_path
        self.embedding_model_name = embedding_model or "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        self.model = SentenceTransformer(self.embedding_model_name)
        self.dimension = 384

        self._load_or_create_index()

    def _load_or_create_index(self):
        """Load or create FAISS index."""
        os.makedirs(self.db_path, exist_ok=True)

        index_path = os.path.join(self.db_path, "faiss_index.bin")
        metadata_path = os.path.join(self.db_path, "metadata.pkl")

        if os.path.exists(index_path) and os.path.exists(metadata_path):
            self.index = faiss.read_index(index_path)
            with open(metadata_path, "rb") as f:
                import pickle

                self.metadata = pickle.load(f)
        else:
            self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata = []

    def add_translation_pair(self, source_text: str, translations: Dict[str, str]) -> ToolResult:
        """Add translation pair to vector database."""
        try:
            embedding = self.model.encode(source_text)
            self.index.add(np.array([embedding]))

            self.metadata.append({"source": source_text, "translations": translations, "embedding": embedding.tolist()})

            self._save_index()

            return ToolResult(success=True, data={"total_pairs": len(self.metadata)})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def search_similar(self, query_text: str, k: int = 5) -> ToolResult:
        """Search for similar translations."""
        if self.index.ntotal == 0:
            return ToolResult(success=True, data={"results": {}})

        try:
            query_embedding = self.model.encode(query_text)
            k = min(k, self.index.ntotal)
            distances, indices = self.index.search(np.array([query_embedding]), k)

            results = {}
            for idx, distance in zip(indices[0], distances[0]):
                if idx < len(self.metadata):
                    item = self.metadata[idx]
                    similarity = 1 / (1 + distance)

                    for lang, trans in item["translations"].items():
                        if lang not in results:
                            results[lang] = []
                        results[lang].append(
                            {"source": item["source"], "translation": trans, "similarity": float(similarity)}
                        )

            return ToolResult(success=True, data={"results": results})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _save_index(self):
        """Save index and metadata."""
        import pickle

        index_path = os.path.join(self.db_path, "faiss_index.bin")
        metadata_path = os.path.join(self.db_path, "metadata.pkl")

        faiss.write_index(self.index, index_path)
        with open(metadata_path, "wb") as f:
            pickle.dump(self.metadata, f)

    def get_statistics(self) -> ToolResult:
        """Get translation memory statistics."""
        lang_counts = {}
        for item in self.metadata:
            for lang in item["translations"].keys():
                lang_counts[lang] = lang_counts.get(lang, 0) + 1

        return ToolResult(success=True, data={"total_items": len(self.metadata), "language_counts": lang_counts})


class TerminologyService:
    """Terminology management service."""

    def __init__(self, db_path: str = "data/terminology"):
        self.db_path = db_path
        self.terminology_file = os.path.join(db_path, "terminology.json")
        self.terminology = self._load_terminology()

    def _load_terminology(self) -> Dict[str, Dict[str, str]]:
        """Load terminology database."""
        os.makedirs(self.db_path, exist_ok=True)

        if os.path.exists(self.terminology_file):
            with open(self.terminology_file, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_terminology(self):
        """Save terminology database."""
        with open(self.terminology_file, "w", encoding="utf-8") as f:
            json.dump(self.terminology, f, ensure_ascii=False, indent=2)

    def add_term(self, term: str, translations: Dict[str, str]) -> ToolResult:
        """Add terminology entry."""
        try:
            self.terminology[term.lower()] = translations
            self._save_terminology()

            return ToolResult(success=True, data={"total_terms": len(self.terminology)})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def get_relevant_terms(self, text: str) -> ToolResult:
        """Get terms relevant to the text."""
        relevant = {}
        text_lower = text.lower()

        for term, translations in self.terminology.items():
            if term in text_lower:
                relevant[term] = translations

        return ToolResult(success=True, data={"terms": relevant})

    def list_terms(self, page: int = 1, per_page: int = 50, search: str = "") -> ToolResult:
        """List terminology entries with pagination."""
        filtered = {}
        search_lower = search.lower()

        for term, trans in self.terminology.items():
            if not search or search_lower in term:
                filtered[term] = trans

        total = len(filtered)
        start = (page - 1) * per_page
        items = list(filtered.items())[start : start + per_page]

        return ToolResult(
            success=True,
            data={
                "terms": [{"term": t, "translations": tr} for t, tr in items],
                "pagination": {"page": page, "per_page": per_page, "total": total},
            },
        )


class EvaluationService:
    """Translation quality evaluation service."""

    def evaluate(
        self,
        source_text: str,
        translated_text: str,
        reference_text: Optional[str] = None,
        metrics: Optional[List[str]] = None,
    ) -> ToolResult:
        """Evaluate translation quality."""
        metrics = metrics or ["bleu", "bert_score", "rouge"]
        results = {}

        if not reference_text:
            results["length_ratio"] = len(translated_text) / len(source_text) if source_text else 0
            results["warning"] = "No reference translation provided. Limited metrics available."
            return ToolResult(success=True, data=results)

        try:
            if "bleu" in metrics:
                from sacrebleu import corpus_bleu

                bleu = corpus_bleu([translated_text], [[reference_text]])
                results["bleu"] = {"score": bleu.score}
        except ImportError:
            results["bleu"] = {"error": "sacrebleu not installed"}
        except Exception as e:
            results["bleu"] = {"error": str(e)}

        try:
            if "bert_score" in metrics:
                from bert_score import score as bert_score

                P, R, F1 = bert_score([translated_text], [reference_text], lang="zh", verbose=False)
                results["bert_score"] = {"precision": float(P[0]), "recall": float(R[0]), "f1": float(F1[0])}
        except ImportError:
            results["bert_score"] = {"error": "bert-score not installed"}
        except Exception as e:
            results["bert_score"] = {"error": str(e)}

        try:
            if "rouge" in metrics:
                from rouge_score import rouge_scorer

                scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
                scores = scorer.score(reference_text, translated_text)
                results["rouge"] = {k: {"fmeasure": v.fmeasure} for k, v in scores.items()}
        except ImportError:
            results["rouge"] = {"error": "rouge-score not installed"}
        except Exception as e:
            results["rouge"] = {"error": str(e)}

        return ToolResult(success=True, data=results)
