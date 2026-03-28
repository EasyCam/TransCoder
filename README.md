# TransCoder

[![PyPI version](https://badge.fury.io/py/transcoder-llm.svg)](https://badge.fury.io/py/transcoder-llm)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Multilingual Parallel Translation Platform with Reflection-based Improvement using Local LLMs**

TransCoder is a powerful translation platform that leverages local Large Language Models (LLMs) through Ollama, featuring innovative **Reflection-based Translation** methods that significantly improve translation quality through AI self-evaluation and iterative refinement.

## Key Features

### 🌟 Core Innovations

- **三省吾身模式 (Three Reflections Mode)**: Translation → AI Reflection → Improvement cycle
- **千锤百炼模式 (Iterative Refinement Mode)**: Configurable 1-10 iteration optimization for maximum quality

### 🚀 Main Features

- **Multilingual Parallel Translation**: Translate to multiple languages simultaneously
- **14 Language Variants**: Including Chinese variants (Simplified, Traditional, Classical)
- **Local LLM Support**: Works with Ollama (Qwen, Llama, Mistral, etc.)
- **Translation Memory**: FAISS-based vector database for consistency
- **Terminology Management**: Professional term consistency across translations
- **Quality Evaluation**: BLEU, BERTScore, ROUGE metrics

## Installation

### From PyPI (Recommended)

```bash
pip install transcoder-llm

# With all features
pip install transcoder-llm[all]

# With specific features
pip install transcoder-llm[web]      # Web interface
pip install transcoder-llm[vector-db] # Translation memory
pip install transcoder-llm[evaluation] # Quality metrics
```

### From Source

```bash
git clone https://github.com/EasyCam/TransCoder.git
cd TransCoder
pip install -e .
```

## Quick Start

### 1. Install and Start Ollama

```bash
# Install Ollama (macOS/Linux)
curl -fsSL https://ollama.ai/install.sh | sh

# Download a model
ollama pull qwen3:0.6b
```

### 2. Start TransCoder

```bash
# Web interface
transcoder web

# Or with production server
transcoder web --production

# CLI translation
transcoder cli -i input.txt -t en,ja,ko -o output.txt
```

### 3. Python API

```python
from transcoder import TransCoderAPI

api = TransCoderAPI(model="qwen3:0.6b")

# Simple translation
result = api.translate("Hello world", "en", ["zh-cn", "ja"])
print(result.data["translations"])

# Reflection mode (三省吾身)
result = api.translate_with_reflection(
    "Hello world", "en", "zh-cn"
)

# Iterative refinement (千锤百炼)
result = api.translate_iterative(
    "Hello world", "en", "zh-cn", iterations=3
)
```

## Translation Modes

### Simple Mode
Fast one-pass translation for everyday use.

### Reflection Mode (三省吾身)
```
Initial Translation → AI Reflection Analysis → Improved Translation
```

The AI analyzes translation quality from four dimensions:
- **Accuracy**: Is the meaning fully preserved?
- **Fluency**: Is the expression natural?
- **Style**: Is the tone appropriate?
- **Terminology**: Are terms translated correctly?

### Iterative Refinement (千锤百炼)
```
Initial → Reflect → Improve → Reflect → Improve → ... → Final
```

Configure 1-10 iterations to balance quality vs. speed.

## API Reference

### REST API

```bash
# Translation
POST /api/translate
{
    "source_text": "Hello world",
    "source_lang": "en",
    "target_langs": ["zh-cn", "ja"]
}

# Reflection
POST /api/translate/reflect
{
    "source_text": "Hello world",
    "translation": "你好世界",
    "source_lang": "en",
    "target_lang": "zh-cn"
}

# Improvement
POST /api/translate/improve
{
    "source_text": "Hello world",
    "current_translation": "你好世界",
    "reflection": "...",
    "source_lang": "en",
    "target_lang": "zh-cn"
}
```

### Python API

```python
from transcoder import TransCoderAPI

api = TransCoderAPI()

# Translate
result = api.translate(text, source_lang, target_langs)

# With reflection
result = api.translate_with_reflection(text, source_lang, target_lang)

# Iterative
result = api.translate_iterative(text, source_lang, target_lang, iterations=3)

# Evaluate quality
result = api.evaluate_translation(source, translated, reference)
```

## Supported Languages

| Code | Language |
|------|----------|
| zh-cn | Chinese (Simplified) |
| zh-tw | Chinese (Traditional) |
| zh-classical-cn | Classical Chinese (Simplified) |
| zh-classical-tw | Classical Chinese (Traditional) |
| en | English |
| ja | Japanese |
| ko | Korean |
| es | Spanish |
| fr | French |
| de | German |
| ru | Russian |
| ar | Arabic |
| pt | Portuguese |

## Project Structure

```
transcoder/
├── __init__.py      # Package exports
├── cli.py           # Command-line interface
├── api.py           # Unified Python API
├── core.py          # Core services
├── app.py           # Flask web application
└── templates/       # HTML templates
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run linter
ruff check transcoder/

# Build package
python -m build

# Upload to PyPI
./upload_pypi.sh
```

## License

MIT License - See [LICENSE](LICENSE) for details.

## Citation

If you use TransCoder in your research, please cite:

```bibtex
@software{transcoder2024,
  title = {TransCoder: Multilingual Parallel Translation Platform with Reflection-based Improvement},
  author = {TransCoder Team},
  year = {2024},
  url = {https://github.com/EasyCam/TransCoder}
}
```

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.