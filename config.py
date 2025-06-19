import os
from dotenv import load_dotenv

load_dotenv()

# Flask配置
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

# Ollama配置
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen3:0.6b')  # 默认使用qwen3:0.6b

# 向量数据库配置
EMBEDDING_MODEL = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
VECTOR_DB_PATH = 'data/vector_db'
TERMINOLOGY_DB_PATH = 'data/terminology'

# 支持的语言
SUPPORTED_LANGUAGES = {
    'zh': '中文',
    'en': 'English',
    'ja': '日本語',
    'ko': '한국어',
    'es': 'Español',
    'fr': 'Français',
    'de': 'Deutsch',
    'ru': 'Русский',
    'ar': 'العربية',
    'pt': 'Português'
}

# 翻译评价指标配置
EVALUATION_METRICS = ['bleu', 'bert_score', 'rouge', 'ter']

# 文件上传配置
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'csv', 'xlsx', 'tmx', 'tbx'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB 