# TransCoder

[![PyPI version](https://badge.fury.io/py/transcoder-llm.svg)](https://badge.fury.io/py/transcoder-llm)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**基于本地大语言模型和反思改进的多语种并行翻译平台**

TransCoder 是一个强大的翻译平台，通过 Ollama 利用本地大语言模型（LLM），创新性地采用**反思式翻译**方法，通过 AI 自我评估和迭代优化显著提升翻译质量。

## 核心亮点

### 🌟 创新功能

- **三省吾身模式**：翻译 → AI反思 → 改进的智能循环
- **千锤百炼模式**：可配置 1-10 次迭代优化，追求极致翻译质量

### 🚀 主要特性

- **多语种并行翻译**：一次输入，多语言同时输出
- **14种语言变体**：包括中文简体、繁体、文言文等变体
- **本地LLM支持**：支持 Ollama（Qwen、Llama、Mistral 等）
- **翻译记忆库**：基于 FAISS 的向量数据库，确保翻译一致性
- **术语库管理**：专业术语统一翻译
- **质量评估**：BLEU、BERTScore、ROUGE 指标

## 安装方法

### 从 PyPI 安装（推荐）

```bash
pip install transcoder-llm

# 安装所有功能
pip install transcoder-llm[all]

# 安装特定功能
pip install transcoder-llm[web]       # Web 界面
pip install transcoder-llm[vector-db] # 翻译记忆库
pip install transcoder-llm[evaluation] # 质量评估
```

### 从源码安装

```bash
git clone https://github.com/EasyCam/TransCoder.git
cd TransCoder
pip install -e .
```

## 快速开始

### 1. 安装并启动 Ollama

```bash
# 安装 Ollama (macOS/Linux)
curl -fsSL https://ollama.ai/install.sh | sh

# 下载模型
ollama pull qwen3:0.6b
```

### 2. 启动 TransCoder

```bash
# Web 界面
transcoder web

# 使用生产服务器
transcoder web --production

# 命令行翻译
transcoder cli -i input.txt -t en,ja,ko -o output.txt
```

### 3. Python API

```python
from transcoder import TransCoderAPI

api = TransCoderAPI(model="qwen3:0.6b")

# 简单翻译
result = api.translate("你好世界", "zh-cn", ["en", "ja"])
print(result.data["translations"])

# 反思模式（三省吾身）
result = api.translate_with_reflection(
    "你好世界", "zh-cn", "en"
)

# 迭代优化（千锤百炼）
result = api.translate_iterative(
    "你好世界", "zh-cn", "en", iterations=3
)
```

## 翻译模式详解

### 简单模式
快速一次性翻译，适合日常使用。

### 反思模式（三省吾身）
```
初始翻译 → AI反思分析 → 改进翻译
```

AI 从四个维度分析翻译质量：
- **准确性**：语义是否完整保留？
- **流畅性**：表达是否自然？
- **风格**：语气是否恰当？
- **术语**：专业术语翻译是否准确？

### 迭代优化（千锤百炼）
```
初始 → 反思 → 改进 → 反思 → 改进 → ... → 最终
```

可配置 1-10 次迭代，灵活平衡质量与速度。

## API 参考

### REST API

```bash
# 翻译
POST /api/translate
{
    "source_text": "你好世界",
    "source_lang": "zh-cn",
    "target_langs": ["en", "ja"]
}

# 反思分析
POST /api/translate/reflect
{
    "source_text": "你好世界",
    "translation": "Hello world",
    "source_lang": "zh-cn",
    "target_lang": "en"
}

# 改进翻译
POST /api/translate/improve
{
    "source_text": "你好世界",
    "current_translation": "Hello world",
    "reflection": "...",
    "source_lang": "zh-cn",
    "target_lang": "en"
}
```

### Python API

```python
from transcoder import TransCoderAPI

api = TransCoderAPI()

# 翻译
result = api.translate(text, source_lang, target_langs)

# 带反思
result = api.translate_with_reflection(text, source_lang, target_lang)

# 迭代优化
result = api.translate_iterative(text, source_lang, target_lang, iterations=3)

# 质量评估
result = api.evaluate_translation(source, translated, reference)
```

## 支持的语言

| 代码 | 语言 |
|------|------|
| zh-cn | 中文大陆地区现代文简体 |
| zh-tw | 中文港澳台地区现代文繁体 |
| zh-classical-cn | 中文文言文简体 |
| zh-classical-tw | 中文文言文繁体 |
| en | English |
| ja | 日本語 |
| ko | 한국어 |
| es | Español |
| fr | Français |
| de | Deutsch |
| ru | Русский |
| ar | العربية |
| pt | Português |

## 项目结构

```
transcoder/
├── __init__.py      # 包导出
├── cli.py           # 命令行接口
├── api.py           # 统一 Python API
├── core.py          # 核心服务
├── app.py           # Flask Web 应用
└── templates/       # HTML 模板
```

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/

# 代码检查
ruff check transcoder/

# 构建包
python -m build

# 上传到 PyPI
./upload_pypi.sh
```

## 许可证

MIT License - 详见 [LICENSE](LICENSE)

## 引用

如果您在研究中使用 TransCoder，请引用：

```bibtex
@software{transcoder2024,
  title = {TransCoder: Multilingual Parallel Translation Platform with Reflection-based Improvement},
  author = {TransCoder Team},
  year = {2024},
  url = {https://github.com/EasyCam/TransCoder}
}
```

## 贡献

欢迎贡献代码！提交 PR 前请阅读贡献指南。