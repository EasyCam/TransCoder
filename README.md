# TransCoder
基于本地Ollama的智能多语种并行翻译工具

## 功能特性

### 核心功能
- **多语种并行翻译**：支持一次输入、多语言同时输出
- **流式文字输出**：实时逐字显示翻译结果，如同在Ollama中直接使用
- **任意篇幅支持**：可处理从短句到长文的各种文本
- **智能语言检测**：自动识别源语言
- **支持10种主流语言**：中文、英语、日语、韩语、西班牙语、法语、德语、俄语、阿拉伯语、葡萄牙语
- **动态模型选择**：从Ollama可用模型中动态选择翻译模型

### 翻译质量提升
- **向量数据库**：使用FAISS构建翻译记忆库，通过相似文本检索提升翻译一致性
- **术语库管理**：支持专业术语的统一翻译，确保术语准确性
- **翻译评价指标**：
  - BLEU分数：评估翻译的准确度
  - BERT Score：基于语义的翻译质量评估
  - ROUGE分数：评估翻译的召回率
  - TER：翻译错误率评估

### 数据导入导出
- **术语库格式支持**：CSV、Excel、TBX（TermBase eXchange）、JSON
- **翻译记忆库支持**：TMX（Translation Memory eXchange）格式
- 符合CAT（计算机辅助翻译）行业标准

## 技术架构

- **后端框架**：Flask
- **LLM引擎**：Ollama（支持多种模型）
- **向量数据库**：FAISS + Sentence-Transformers
- **前端技术**：Bootstrap 5 + Vanilla JavaScript
- **翻译评估**：SacreBLEU、BERTScore、ROUGE

## 安装部署

### 1. 环境要求
- Python 3.8+
- Ollama（需要先安装并运行）
- 8GB+ RAM（推荐16GB）

### 2. 安装Ollama
```bash
# Windows
# 访问 https://ollama.ai 下载安装

# macOS/Linux
curl -fsSL https://ollama.ai/install.sh | sh
```

### 3. 下载模型
```bash
# 下载推荐的模型（选择其一）
ollama pull qwen3:0.6b       # 阿里通义千问3（默认，轻量级）
ollama pull qwen2:1.5b       # 阿里通义千问2（平衡型）
ollama pull qwen2:7b         # 阿里通义千问2（高质量）
ollama pull llama3.2:1b      # Meta Llama 3.2（轻量级）
ollama pull mistral          # Mistral AI的模型
```

### 4. 安装TransCoder
```bash
# 克隆项目
git clone https://github.com/yourusername/TransCoder.git
cd TransCoder

# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 5. 配置环境
创建 `.env` 文件：
```bash
# Flask配置
SECRET_KEY=your-secret-key-here
DEBUG=False

# Ollama配置
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen3:0.6b  # 默认模型，可在界面中动态切换
```

### 6. 启动服务
```bash
# 开发模式
python run.py

# 生产模式
python run.py
```

访问 http://localhost:5000 即可使用

## 使用指南

### 基本翻译流程
1. 在左侧文本框输入要翻译的内容
2. 选择源语言（或使用自动检测）
3. 点击"添加语言"按钮添加目标语言
4. 在高级选项中选择要使用的Ollama模型
5. 可选择是否启用"流式输出"（默认开启）
6. 点击中间的翻译按钮
7. 在右侧查看翻译结果

### 🔥 流式文字输出
- **实时翻译体验**：开启流式输出后，翻译文字会像在Ollama中直接生成那样逐字显示
- **可选择模式**：支持传统翻译模式和流式翻译模式切换
- **直观的视觉反馈**：通过颜色变化和状态指示器显示翻译进度
- **智能停止控制**：提供停止按钮，可以随时中断正在进行的翻译
- **性能监控**：实时显示tokens/s和翻译用时等性能指标

### 模型选择
- 系统会自动加载所有可用的Ollama模型
- 模型列表按名称排序显示
- 默认使用 `qwen3:0.6b` 模型
- 可以随时切换不同的模型进行翻译

### 术语库管理
1. 点击顶部"术语库"按钮
2. 可以：
   - 手动添加术语及其翻译
   - 导入CSV/Excel/TBX格式的术语表
   - 导出现有术语库

### 翻译记忆库
1. 点击顶部"翻译记忆库"按钮
2. 可以：
   - 将当前翻译添加到记忆库
   - 导入TMX格式的翻译记忆
   - 导出翻译记忆为TMX格式

### 翻译质量评估
点击每个翻译结果下方的"评估质量"按钮，系统会计算：
- 综合评分（0-100）
- BLEU分数
- BERT语义相似度
- ROUGE召回率

## API接口

### 翻译接口
```bash
POST /api/translate
Content-Type: application/json

{
    "source_text": "你好世界",
    "source_lang": "zh",
    "target_langs": ["en", "ja", "ko"],
    "use_vector_db": true,
    "use_terminology": true,
    "model": "qwen3:0.6b"  # 可选，指定使用的模型
}
```

### 流式翻译接口
```bash
POST /api/translate/stream
Content-Type: application/json

{
    "source_text": "你好世界",
    "source_lang": "zh",
    "target_langs": ["en", "ja", "ko"],
    "use_vector_db": true,
    "use_terminology": true,
    "model": "qwen3:0.6b"
}

# 返回 Server-Sent Events (SSE) 流：
data: {"type": "init", "source_text": "你好世界", ...}
data: {"type": "start", "target_lang": "en", "model_used": "qwen3:0.6b"}
data: {"type": "content", "target_lang": "en", "content": "Hello", "full_content": "Hello"}
data: {"type": "content", "target_lang": "en", "content": " world", "full_content": "Hello world"}
data: {"type": "complete", "target_lang": "en", "final_content": "Hello world"}
data: {"type": "finished"}
```

### 评估接口
```bash
POST /api/evaluate
Content-Type: application/json

{
    "source_text": "原文",
    "translated_text": "翻译",
    "reference_text": "参考译文",
    "metrics": ["bleu", "bert_score", "rouge"]
}
```

### 获取模型列表
```bash
GET /api/models

响应:
{
    "models": ["qwen3:0.6b", "qwen2:1.5b", "llama3.2:1b", ...],
    "default": "qwen3:0.6b"
}
```

## 性能优化建议

1. **模型选择**：
   - 速度优先：使用较小的模型如 qwen3:0.6b 或 llama3.2:1b
   - 质量优先：使用较大的模型如 qwen2:7b 或 llama3.2:3b

2. **硬件配置**：
   - GPU加速：如有NVIDIA GPU，Ollama会自动使用
   - 内存：翻译长文本时建议16GB+内存

3. **批量处理**：
   - 使用翻译记忆库缓存常见翻译
   - 导入行业术语库提升专业领域翻译质量

## 常见问题

**Q: Ollama连接失败？**
A: 确保Ollama服务正在运行，可以通过 `ollama list` 检查

**Q: 翻译速度慢？**
A: 1) 使用较小的模型 2) 启用GPU加速 3) 减少并行翻译的语言数

**Q: 如何提升翻译质量？**
A: 1) 导入相关领域的术语库 2) 积累翻译记忆库 3) 选择更适合的模型

**Q: 模型列表为空？**
A: 确保已经通过 `ollama pull` 下载了至少一个模型

## 开发计划

- [ ] 支持更多语言
- [ ] 批量文档翻译
- [ ] 实时协作翻译
- [ ] 翻译API限流和认证
- [ ] Docker容器化部署
- [ ] 更多CAT工具格式支持

## 贡献指南

欢迎提交Issue和Pull Request！

## 许可证

MIT License
