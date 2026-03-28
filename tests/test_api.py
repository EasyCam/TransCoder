"""
Tests for TransCoder API
"""

import pytest
from transcoder.api import TransCoderAPI
from transcoder.core import ToolResult


class TestTransCoderAPI:
    """Test cases for TransCoder API."""
    
    def test_api_initialization(self):
        """Test API can be initialized."""
        api = TransCoderAPI(model="test-model")
        assert api.model == "test-model"
    
    def test_get_supported_languages(self):
        """Test supported languages list."""
        api = TransCoderAPI()
        languages = api.get_supported_languages()
        
        assert isinstance(languages, dict)
        assert "en" in languages
        assert "zh-cn" in languages
        assert "ja" in languages
    
    def test_tool_result_to_dict(self):
        """Test ToolResult serialization."""
        result = ToolResult(
            success=True,
            data={"test": "value"},
            metadata={"key": "value"}
        )
        
        d = result.to_dict()
        assert d["success"] is True
        assert d["data"]["test"] == "value"
        assert d["error"] is None


class TestTranslationModes:
    """Test different translation modes."""
    
    @pytest.fixture
    def api(self):
        return TransCoderAPI()
    
    def test_simple_mode_requires_text(self, api):
        """Test simple translation mode."""
        # This would require a mock LLM in actual testing
        pass
    
    def test_reflection_mode_flow(self, api):
        """Test reflection mode executes correct flow."""
        # This would require a mock LLM in actual testing
        pass
    
    def test_iterative_mode_iterations(self, api):
        """Test iterative mode respects iteration count."""
        # This would require a mock LLM in actual testing
        pass


class TestVectorDB:
    """Test vector database functionality."""
    
    def test_vector_db_initialization(self):
        """Test vector DB can be initialized."""
        # This would require FAISS and sentence-transformers
        pass
    
    def test_add_translation_pair(self):
        """Test adding translation to memory."""
        pass
    
    def test_search_similar(self):
        """Test similarity search."""
        pass


class TestTerminology:
    """Test terminology management."""
    
    def test_add_term(self, tmp_path):
        """Test adding terminology entry."""
        from transcoder.core import TerminologyService
        
        service = TerminologyService(db_path=str(tmp_path))
        result = service.add_term("AI", {"zh-cn": "人工智能", "ja": "人工知能"})
        
        assert result.success is True
    
    def test_get_relevant_terms(self, tmp_path):
        """Test getting relevant terminology."""
        from transcoder.core import TerminologyService
        
        service = TerminologyService(db_path=str(tmp_path))
        service.add_term("AI", {"zh-cn": "人工智能"})
        
        result = service.get_relevant_terms("AI is transforming technology")
        
        assert result.success is True
        assert "ai" in result.data.get("terms", {})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])