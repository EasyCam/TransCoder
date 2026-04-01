"""
TransCoder - Multilingual Parallel Translation Platform with Reflection-based Improvement

A Flask-based multilingual parallel translation platform using local LLMs (Ollama).
Features reflection-based translation improvement, vector database for translation memory,
terminology management, and translation quality evaluation.
"""

__version__ = "1.0.0"
__author__ = "TransCoder Team"
__email__ = "transcoder@example.com"
__license__ = "MIT"

from transcoder.api import TransCoderAPI
from transcoder.core import EvaluationService, TerminologyService, TranslationService, VectorDBService

__all__ = [
    "TransCoderAPI",
    "TranslationService",
    "VectorDBService",
    "TerminologyService",
    "EvaluationService",
    "__version__",
]
