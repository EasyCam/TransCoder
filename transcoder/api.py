"""
TransCoder Unified API

Provides a unified Python API for all TransCoder functionality.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import time

from transcoder.core import (
    TranslationService,
    VectorDBService,
    TerminologyService,
    EvaluationService,
    ToolResult
)


class TransCoderAPI:
    """
    Unified API for TransCoder translation platform.
    
    Usage:
        api = TransCoderAPI(model="qwen3:0.6b")
        
        # Simple translation
        result = api.translate("Hello", "en", ["zh-cn", "ja"])
        
        # Reflection translation (三省吾身)
        result = api.translate_with_reflection("Hello", "en", "zh-cn")
        
        # Iterative refinement (千锤百炼)
        result = api.translate_iterative("Hello", "en", "zh-cn", iterations=3)
    """
    
    def __init__(
        self,
        model: str = "qwen3:0.6b",
        ollama_host: str = "http://localhost:11434",
        vector_db_path: str = "data/vector_db",
        terminology_path: str = "data/terminology"
    ):
        """
        Initialize TransCoder API.
        
        Args:
            model: Default Ollama model to use
            ollama_host: Ollama server address
            vector_db_path: Path for translation memory storage
            terminology_path: Path for terminology database
        """
        self.model = model
        self.ollama_host = ollama_host
        
        self.translation_service = TranslationService(model=model, ollama_host=ollama_host)
        
        self._vector_db: Optional[VectorDBService] = None
        self._terminology: Optional[TerminologyService] = None
        self._evaluation: Optional[EvaluationService] = None
        
        self._vector_db_path = vector_db_path
        self._terminology_path = terminology_path
    
    @property
    def vector_db(self) -> VectorDBService:
        """Lazy-loaded vector database service."""
        if self._vector_db is None:
            self._vector_db = VectorDBService(db_path=self._vector_db_path)
        return self._vector_db
    
    @property
    def terminology(self) -> TerminologyService:
        """Lazy-loaded terminology service."""
        if self._terminology is None:
            self._terminology = TerminologyService(db_path=self._terminology_path)
        return self._terminology
    
    @property
    def evaluation(self) -> EvaluationService:
        """Lazy-loaded evaluation service."""
        if self._evaluation is None:
            self._evaluation = EvaluationService()
        return self._evaluation
    
    def get_available_models(self) -> ToolResult:
        """Get list of available Ollama models."""
        models = self.translation_service.get_available_models()
        return ToolResult(
            success=True,
            data={"models": models, "default": self.model}
        )
    
    def detect_language(self, text: str) -> ToolResult:
        """Detect language of text."""
        lang = self.translation_service.detect_language(text)
        return ToolResult(success=True, data={"language": lang})
    
    def translate(
        self,
        source_text: str,
        source_lang: str,
        target_langs: List[str],
        mode: str = "simple",
        model: Optional[str] = None,
        use_vector_db: bool = False,
        use_terminology: bool = False,
        iterations: int = 1
    ) -> ToolResult:
        """
        Translate text with various modes.
        
        Args:
            source_text: Text to translate
            source_lang: Source language code (use "auto" for auto-detection)
            target_langs: List of target language codes
            mode: Translation mode:
                - "simple": Fast one-pass translation
                - "reflect": Single reflection (三省吾身 single round)
                - "iterate": Multi-round refinement (千锤百炼)
            model: Model to use (defaults to instance model)
            use_vector_db: Use translation memory
            use_terminology: Use terminology database
            iterations: Number of iterations for "iterate" mode (1-10)
        
        Returns:
            ToolResult with translations and metadata
        """
        model = model or self.model
        
        vector_db_svc = self.vector_db if use_vector_db else None
        terminology_svc = self.terminology if use_terminology else None
        
        if mode == "simple":
            return self.translation_service.translate(
                source_text=source_text,
                source_lang=source_lang,
                target_langs=target_langs,
                model=model,
                use_vector_db=use_vector_db,
                use_terminology=use_terminology,
                vector_db_service=vector_db_svc,
                terminology_service=terminology_svc
            )
        
        elif mode in ("reflect", "iterate"):
            results = {}
            
            for target_lang in target_langs:
                iters = iterations if mode == "iterate" else 1
                result = self.translation_service.translate_with_reflection(
                    source_text=source_text,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    model=model,
                    iterations=iters
                )
                if result.success:
                    results[target_lang] = result.data
                else:
                    results[target_lang] = {"error": result.error}
            
            return ToolResult(
                success=True,
                data={"translations": results}
            )
        
        else:
            return ToolResult(
                success=False,
                error=f"Unknown mode: {mode}. Use 'simple', 'reflect', or 'iterate'."
            )
    
    def translate_with_reflection(
        self,
        source_text: str,
        source_lang: str,
        target_lang: str,
        model: Optional[str] = None,
        iterations: int = 1
    ) -> ToolResult:
        """
        Translate with reflection-based improvement (三省吾身模式).
        
        This is the signature innovation of TransCoder:
        Initial translation -> AI reflection -> Improved translation
        
        The AI analyzes accuracy, fluency, style, and terminology,
        then generates an improved translation based on its analysis.
        
        Args:
            source_text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            model: Model to use
            iterations: Number of reflection-improvement cycles
        
        Returns:
            ToolResult with translation and reflection history
        """
        return self.translation_service.translate_with_reflection(
            source_text=source_text,
            source_lang=source_lang,
            target_lang=target_lang,
            model=model or self.model,
            iterations=iterations
        )
    
    def translate_iterative(
        self,
        source_text: str,
        source_lang: str,
        target_lang: str,
        model: Optional[str] = None,
        iterations: int = 3
    ) -> ToolResult:
        """
        Iterative refinement translation (千锤百炼模式).
        
        This allows users to configure the number of improvement cycles
        for maximum translation quality. More iterations = better quality
        but longer processing time.
        
        Args:
            iterations: Number of refinement iterations (1-10)
        
        Returns:
            ToolResult with final translation and full improvement history
        """
        return self.translate_with_reflection(
            source_text=source_text,
            source_lang=source_lang,
            target_lang=target_lang,
            model=model,
            iterations=min(max(1, iterations), 10)
        )
    
    def reflect_translation(
        self,
        source_text: str,
        translation: str,
        source_lang: str,
        target_lang: str,
        model: Optional[str] = None
    ) -> ToolResult:
        """
        Analyze translation quality (反思翻译).
        
        The AI examines:
        - Accuracy: Is the meaning preserved?
        - Fluency: Is the expression natural?
        - Style: Is the tone appropriate?
        - Terminology: Are terms correct?
        """
        return self.translation_service.reflect_translation(
            source_text=source_text,
            translation=translation,
            source_lang=source_lang,
            target_lang=target_lang,
            model=model or self.model
        )
    
    def improve_translation(
        self,
        source_text: str,
        current_translation: str,
        reflection: str,
        source_lang: str,
        target_lang: str,
        model: Optional[str] = None
    ) -> ToolResult:
        """
        Improve translation based on reflection analysis.
        """
        return self.translation_service.improve_translation(
            source_text=source_text,
            current_translation=current_translation,
            reflection=reflection,
            source_lang=source_lang,
            target_lang=target_lang,
            model=model or self.model
        )
    
    def add_translation_memory(
        self,
        source_text: str,
        translations: Dict[str, str]
    ) -> ToolResult:
        """Add translation to memory database."""
        return self.vector_db.add_translation_pair(
            source_text=source_text,
            translations=translations
        )
    
    def search_similar_translations(
        self,
        query_text: str,
        k: int = 5
    ) -> ToolResult:
        """Search for similar translations in memory."""
        return self.vector_db.search_similar(query_text=query_text, k=k)
    
    def add_terminology(
        self,
        term: str,
        translations: Dict[str, str]
    ) -> ToolResult:
        """Add terminology entry."""
        return self.terminology.add_term(term=term, translations=translations)
    
    def get_relevant_terminology(self, text: str) -> ToolResult:
        """Get terminology relevant to text."""
        return self.terminology.get_relevant_terms(text=text)
    
    def evaluate_translation(
        self,
        source_text: str,
        translated_text: str,
        reference_text: Optional[str] = None,
        metrics: Optional[List[str]] = None
    ) -> ToolResult:
        """Evaluate translation quality."""
        return self.evaluation.evaluate(
            source_text=source_text,
            translated_text=translated_text,
            reference_text=reference_text,
            metrics=metrics
        )
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Get dictionary of supported languages."""
        return TranslationService.SUPPORTED_LANGUAGES