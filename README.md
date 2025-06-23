# TransCoder-基于本地大语言模型和反思改进的多语种并行翻译平台

版本号：1.0

## 功能特性

### 核心功能
- **多语种并行翻译**：支持一次输入、多语言同时输出
- **多种翻译模式**：
  - **简单快速翻译**：传统一次性翻译，速度最快
  - **流式文字输出**：实时逐字显示翻译结果，如同在Ollama中直接使用
  - **反思翻译模式**：翻译→反思→优化，AI自我改进提升质量
  - **三省吾身模式**：连续两轮反思优化，追求更高质量
  - **千锤百炼模式**：自定义优化次数（1-10次），追求完美翻译
- **任意篇幅支持**：可处理从短句到长文的各种文本
- **智能语言检测**：自动识别源语言
- **支持14种语言变体**：中文大陆地区现代文简体、中文港澳台地区现代文繁体、中文文言文简体、中文文言文繁体、英语、日语、韩语、西班牙语、法语、德语、俄语、阿拉伯语、葡萄牙语
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
ollama pull qwen3:4b       # 阿里通义千问2（平衡型）
ollama pull qwen3:8b        # 阿里通义千问2（高质量）
ollama pull llama3.2:1b      # Meta Llama 3.2（轻量级）
ollama pull mistral          # Mistral AI的模型
```

### 4. 安装TransCoder
```bash
# 克隆项目
git clone https://github.com/EasyCam/TransCoder.git
cd TransCoder

# 智能安装依赖（自动检测现有包，避免环境冲突）
pip install -r requirements-minimal.txt

# 如果您有完整的PyTorch/TensorFlow环境，可以安装完整版本
pip install -r requirements.txt
```

**环境保护说明：**
- `requirements-minimal.txt` 包含最少必需的依赖，避免与现有torch等环境冲突
- 安装脚本会自动检测已有的Python包，跳过已安装的包
- 支持与现有机器学习环境共存

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

访问 http://localhost:6000 即可使用

## 使用指南

### 基本翻译流程
1. 在左侧文本框输入要翻译的内容
2. 选择源语言（或使用自动检测，支持中文变体智能识别）
3. 点击"添加语言"按钮添加目标语言
4. 在高级选项中选择翻译模式和Ollama模型
5. 点击中间的翻译按钮进行批量翻译
6. 在右侧查看翻译结果

### 🚀 翻译模式详解

#### 简单快速翻译
- **特点**：传统一次性翻译，速度最快
- **适用场景**：日常快速翻译、大量文本处理
- **优势**：速度快，资源消耗少

#### 流式输出翻译  
- **特点**：实时显示翻译过程，支持性能监控
- **适用场景**：观察翻译过程、长文本翻译
- **优势**：可视化进度，支持中途停止

#### 反思翻译模式
- **工作流程**：初始翻译 → AI反思分析 → 优化改进
- **特点**：AI自我评估和改进，提升翻译质量
- **适用场景**：重要文档翻译、质量要求较高的内容
- **优势**：自动质量提升，减少人工校对

#### 三省吾身模式
- **工作流程**：初始翻译 → 第一轮反思优化 → 第二轮反思优化
- **特点**：连续两轮AI自我改进
- **适用场景**：专业文档、学术论文、商务合同
- **优势**：更高的翻译质量和准确性

#### 千锤百炼模式
- **工作流程**：初始翻译 → 多轮反思优化（用户自定义次数）
- **特点**：可自定义1-10次优化轮数，追求完美
- **适用场景**：顶级质量要求、重要公文、文学作品
- **优势**：极致的翻译质量，可根据需求调整优化强度

### ⚡ 灵活翻译操作
- **批量翻译**：使用中间的大翻译按钮一次性翻译所有语言
- **单独翻译**：使用每个语言区域的"重新翻译"按钮，可以：
  - 更换目标语言后重新翻译该语言
  - 修改源文本后只重新翻译特定语言
  - 尝试不同的翻译结果
- **实时切换**：更改语言选择后可立即重新翻译，无需重置整个页面

### 🎯 中文变体支持
- **中文大陆地区现代文简体**：中国大陆使用的现代简化字符和当代表达方式
- **中文港澳台地区现代文繁体**：港澳台地区使用的繁体字符和表达习惯
- **中文文言文简体**：古典文学风格、古代语法模式，使用简化字符
- **中文文言文繁体**：古典文学风格、古代语法模式，使用传统繁体字符
- **智能检测**：自动检测功能可区分不同的中文变体

### 🔥 流式文字输出
- **实时翻译体验**：开启流式输出后，翻译文字会像在Ollama中直接生成那样逐字显示
- **可选择模式**：支持传统翻译模式和流式翻译模式切换
- **直观的视觉反馈**：通过颜色变化和状态指示器显示翻译进度
- **智能停止控制**：提供停止按钮，可以随时中断正在进行的翻译
- **性能监控**：实时显示tokens/s和翻译用时等性能指标
- **单独语言翻译**：每个语言区域都有独立的重新翻译按钮，可单独重新翻译特定语言

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

### 反思翻译接口
```bash
POST /api/translate/reflect
Content-Type: application/json

{
    "source_text": "你好世界",
    "translation": "Hello world",
    "source_lang": "zh",
    "target_lang": "en",
    "model": "qwen3:0.6b"
}

响应:
{
    "reflection": "翻译基本准确，但可以考虑更自然的表达方式..."
}
```

### 改进翻译接口
```bash
POST /api/translate/improve
Content-Type: application/json

{
    "source_text": "你好世界",
    "current_translation": "Hello world",
    "reflection": "翻译基本准确，但可以考虑更自然的表达方式...",
    "source_lang": "zh",
    "target_lang": "en",
    "model": "qwen3:0.6b"
}

响应:
{
    "improved_translation": "Hello, world!"
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

**性能指标说明**：
- `token_count`: 当前已生成的token数量
- `elapsed_time`: 已用时间（秒）
- `tokens_per_second`: 实时生成速度（tokens/秒）
- `total_tokens`: 最终生成的总token数
- `total_time`: 总翻译用时（秒）

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
    "models": ["qwen3:0.6b", "qwen3:4b", "llama3.2:1b", ...],
    "default": "qwen3:0.6b"
}
```

## 性能优化建议

1. **模型选择**：
   - 速度优先：使用较小的模型如 qwen3:0.6b 或 llama3.2:1b
   - 质量优先：使用较大的模型如 qwen3:8b或 llama3.2:3b

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
