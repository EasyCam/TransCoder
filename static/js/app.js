// 全局变量
let currentTranslations = {};
let defaultModel = 'qwen3:0.6b';
let isTranslating = false;
let translationAbortController = null;

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    // 监听源文本变化
    const sourceText = document.getElementById('sourceText');
    sourceText.addEventListener('input', function() {
        document.getElementById('charCount').textContent = this.value.length;
    });
    
    // 监听翻译模式变化
    const translationModeSelect = document.getElementById('translationMode');
    translationModeSelect.addEventListener('change', function() {
        toggleIterativeCountContainer();
    });
    
    // 加载可用的Ollama模型
    loadAvailableModels();
});

// 切换优化次数选择器的显示
function toggleIterativeCountContainer() {
    const mode = document.getElementById('translationMode').value;
    const container = document.getElementById('iterativeCountContainer');
    
    if (mode === 'iterative') {
        container.style.display = 'block';
    } else {
        container.style.display = 'none';
    }
}

// 加载可用的Ollama模型
async function loadAvailableModels() {
    const select = document.getElementById('ollamaModel');
    
    try {
        // 显示加载状态
        select.innerHTML = '<option value="">正在加载模型...</option>';
        select.disabled = true;
        
        const response = await axios.get('/api/models');
        
        // 清空选项
        select.innerHTML = '';
        select.disabled = false;
        
        // 获取模型列表和默认模型
        const models = response.data.models || [];
        defaultModel = response.data.default || 'qwen3:0.6b';
        
        console.log('Available models:', models);
        console.log('Default model:', defaultModel);
        
        // 如果没有可用模型，显示提示
        if (models.length === 0) {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = '没有可用的模型 - 请先安装模型';
            select.appendChild(option);
            select.disabled = true;
            
            // 显示帮助信息
            showModelInstallationHelp();
            return;
        }
        
        // 添加模型选项
        models.forEach(model => {
            const option = document.createElement('option');
            option.value = model;
            option.textContent = model;
            // 设置默认选中的模型
            if (model === defaultModel) {
                option.selected = true;
            }
            select.appendChild(option);
        });
        
        // 如果默认模型不在列表中，选择第一个模型
        if (!models.includes(defaultModel) && models.length > 0) {
            select.value = models[0];
            console.log(`Default model ${defaultModel} not found, using ${models[0]}`);
        }
        
    } catch (error) {
        console.error('Failed to load models:', error);
        
        // 根据错误类型显示不同的提示
        select.innerHTML = '';
        select.disabled = true;
        
        let errorMessage = '无法获取模型列表';
        
        if (error.code === 'ERR_NETWORK' || error.message.includes('Network Error')) {
            errorMessage = 'Ollama服务未运行';
        } else if (error.response?.status === 500) {
            errorMessage = 'Ollama连接失败';
        }
        
        const option = document.createElement('option');
        option.value = '';
        option.textContent = errorMessage;
        select.appendChild(option);
        
        // 显示详细的错误帮助
        showConnectionErrorHelp(error);
    }
}

// 显示模型安装帮助信息
function showModelInstallationHelp() {
    const helpDiv = document.createElement('div');
    helpDiv.className = 'alert alert-warning mt-2';
    helpDiv.innerHTML = `
        <h6><i class="bi bi-exclamation-triangle"></i> 没有找到可用的模型</h6>
        <p>请先安装Ollama模型。推荐安装命令：</p>
        <code>ollama pull qwen3:0.6b</code><br>
        <small class="text-muted">或者安装其他模型如：llama3.2:1b, qwen2:1.5b 等</small>
        <button class="btn btn-sm btn-outline-primary mt-2" onclick="retryLoadModels()">
            <i class="bi bi-arrow-clockwise"></i> 重新检测模型
        </button>
    `;
    
    // 插入到模型选择器下方
    const modelContainer = document.getElementById('ollamaModel').parentElement;
    const existingHelp = modelContainer.querySelector('.alert');
    if (existingHelp) {
        existingHelp.remove();
    }
    modelContainer.appendChild(helpDiv);
}

// 显示连接错误帮助信息
function showConnectionErrorHelp(error) {
    const helpDiv = document.createElement('div');
    helpDiv.className = 'alert alert-danger mt-2';
    
    let helpContent = `
        <h6><i class="bi bi-exclamation-circle"></i> Ollama连接失败</h6>
        <p>请检查以下事项：</p>
        <ul>
            <li>确保Ollama服务正在运行</li>
            <li>检查Ollama是否在默认端口11434运行</li>
            <li>尝试在终端运行：<code>ollama list</code></li>
        </ul>
    `;
    
    if (error.code === 'ERR_NETWORK') {
        helpContent += `
            <p><strong>网络错误：</strong>无法连接到Ollama服务</p>
            <p>请确保Ollama已安装并正在运行：</p>
            <code>ollama serve</code>
        `;
    }
    
    helpContent += `
        <button class="btn btn-sm btn-outline-danger mt-2" onclick="retryLoadModels()">
            <i class="bi bi-arrow-clockwise"></i> 重试连接
        </button>
    `;
    
    helpDiv.innerHTML = helpContent;
    
    // 插入到模型选择器下方
    const modelContainer = document.getElementById('ollamaModel').parentElement;
    const existingHelp = modelContainer.querySelector('.alert');
    if (existingHelp) {
        existingHelp.remove();
    }
    modelContainer.appendChild(helpDiv);
}

// 重试加载模型
function retryLoadModels() {
    // 移除现有的帮助信息
    const modelContainer = document.getElementById('ollamaModel').parentElement;
    const existingHelp = modelContainer.querySelector('.alert');
    if (existingHelp) {
        existingHelp.remove();
    }
    
    // 重新加载模型
    loadAvailableModels();
}

// 翻译文本
async function translateText() {
    const sourceText = document.getElementById('sourceText').value;
    const sourceLang = document.getElementById('sourceLang').value;
    const useVectorDB = document.getElementById('useVectorDB').checked;
    const useTerminology = document.getElementById('useTerminology').checked;
    const translationMode = document.getElementById('translationMode').value;
    const selectedModel = document.getElementById('ollamaModel').value;
    
    if (!sourceText.trim()) {
        alert('请输入要翻译的文本');
        return;
    }
    
    if (!selectedModel) {
        alert('请先选择或安装Ollama模型');
        return;
    }
    
    // 获取所有目标语言
    const targetLangs = [];
    document.querySelectorAll('.target-lang-select').forEach(select => {
        targetLangs.push(select.value);
    });
    
    if (targetLangs.length === 0) {
        alert('请至少选择一种目标语言');
        return;
    }
    
    // 设置翻译状态
    isTranslating = true;
    updateTranslationButtons();
    
    // 清空之前的翻译结果和性能指标
    document.querySelectorAll('.translation-result').forEach(textarea => {
        textarea.value = '';
        textarea.style.backgroundColor = '#f8f9fa';
    });
    
    document.querySelectorAll('.performance-metrics').forEach(metrics => {
        metrics.style.display = 'none';
    });
    
    try {
        // 根据翻译模式选择不同的翻译方法
        switch (translationMode) {
            case 'simple':
                await translateTextTraditional(sourceText, sourceLang, targetLangs, useVectorDB, useTerminology, selectedModel);
                break;
            case 'streaming':
                await translateTextStreaming(sourceText, sourceLang, targetLangs, useVectorDB, useTerminology, selectedModel);
                break;
            case 'reflection':
                await translateTextReflection(sourceText, sourceLang, targetLangs, useVectorDB, useTerminology, selectedModel, 1);
                break;
            case 'triple':
                await translateTextReflection(sourceText, sourceLang, targetLangs, useVectorDB, useTerminology, selectedModel, 2);
                break;
            case 'iterative':
                const iterativeCount = parseInt(document.getElementById('iterativeCount').value);
                await translateTextReflection(sourceText, sourceLang, targetLangs, useVectorDB, useTerminology, selectedModel, iterativeCount);
                break;
            default:
                await translateTextTraditional(sourceText, sourceLang, targetLangs, useVectorDB, useTerminology, selectedModel);
        }
        
    } catch (error) {
        if (error.name === 'AbortError') {
            console.log('Translation was stopped by user');
        } else {
            let errorMsg = '翻译失败: ';
            
            if (error.message.includes('Network Error') || error.message.includes('Failed to fetch')) {
                errorMsg += 'Ollama服务连接失败，请确保服务正在运行';
            } else if (error.response?.data?.error) {
                errorMsg += error.response.data.error;
            } else {
                errorMsg += error.message;
            }
            
            alert(errorMsg);
        }
    } finally {
        isTranslating = false;
        translationAbortController = null;
        updateTranslationButtons();
    }
}

// 传统翻译函数
async function translateTextTraditional(sourceText, sourceLang, targetLangs, useVectorDB, useTerminology, selectedModel) {
    const response = await axios.post('/api/translate', {
        source_text: sourceText,
        source_lang: sourceLang,
        target_langs: targetLangs,
        use_vector_db: useVectorDB,
        use_terminology: useTerminology,
        model: selectedModel
    });
    
    currentTranslations = response.data;
    displayTranslations(response.data);
}

// 流式翻译函数
async function translateTextStreaming(sourceText, sourceLang, targetLangs, useVectorDB, useTerminology, selectedModel) {
    // 创建AbortController用于停止请求
    translationAbortController = new AbortController();
    
    // 由于EventSource不支持POST，我们使用fetch的stream功能
    const response = await fetch('/api/translate/stream', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            source_text: sourceText,
            source_lang: sourceLang,
            target_langs: targetLangs,
            use_vector_db: useVectorDB,
            use_terminology: useTerminology,
            model: selectedModel
        }),
        signal: translationAbortController.signal
    });
    
    if (!response.ok) {
        throw new Error('翻译请求失败');
    }
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    
    // 存储每种语言的翻译状态
    const translationStates = {};
    targetLangs.forEach(lang => {
        translationStates[lang] = {
            content: '',
            textarea: null,
            completed: false,
            startTime: null,
            tokenCount: 0
        };
    });
    
    // 获取对应的textarea元素
    document.querySelectorAll('.target-lang-item').forEach((item, index) => {
        const lang = item.querySelector('.target-lang-select').value;
        if (targetLangs.includes(lang)) {
            translationStates[lang].textarea = item.querySelector('.translation-result');
            translationStates[lang].container = item;
            translationStates[lang].performanceDiv = item.querySelector('.performance-metrics');
            
            // 确保性能指标区域存在
            if (!translationStates[lang].performanceDiv) {
                const performanceDiv = document.createElement('div');
                performanceDiv.className = 'performance-metrics mt-2';
                performanceDiv.style.display = 'none';
                performanceDiv.innerHTML = `
                    <small class="text-muted d-flex justify-content-between">
                        <span class="tokens-per-second"></span>
                        <span class="translation-time"></span>
                    </small>
                `;
                
                // 插入到按钮行之后
                const buttonRow = item.querySelector('.mt-2');
                if (buttonRow && buttonRow.nextSibling) {
                    item.insertBefore(performanceDiv, buttonRow.nextSibling);
                } else {
                    item.appendChild(performanceDiv);
                }
                
                translationStates[lang].performanceDiv = performanceDiv;
            }
            
            // 添加状态指示器
            let statusIndicator = item.querySelector('.stream-status');
            if (!statusIndicator) {
                statusIndicator = document.createElement('div');
                statusIndicator.className = 'stream-status waiting';
                statusIndicator.textContent = '等待中';
                item.appendChild(statusIndicator);
            }
            translationStates[lang].statusIndicator = statusIndicator;
            
            // 设置初始状态
            translationStates[lang].textarea.className = 'form-control translation-result translation-streaming';
            translationStates[lang].textarea.placeholder = '等待翻译...';
            

        }
    });
    
    try {
        while (true) {
            const { done, value } = await reader.read();
            
            if (done) break;
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        await handleStreamData(data, translationStates);
                    } catch (e) {
                        console.error('解析流数据失败:', e);
                    }
                }
            }
        }
    } finally {
        reader.releaseLock();
    }
}

// 处理流式数据
async function handleStreamData(data, translationStates) {
    switch (data.type) {
        case 'init':
            console.log('翻译开始:', data);
            break;
            
        case 'start':
            console.log(`开始翻译到 ${data.target_lang}`);
            if (translationStates[data.target_lang]) {
                const state = translationStates[data.target_lang];
                state.textarea.className = 'form-control translation-result translation-active typing-cursor';
                state.textarea.placeholder = '正在翻译中...';
                state.statusIndicator.className = 'stream-status translating';
                state.statusIndicator.textContent = '翻译中';
                state.startTime = data.start_time || Date.now() / 1000;
            }
            break;
            
        case 'content':
            if (translationStates[data.target_lang] && !translationStates[data.target_lang].completed) {
                const state = translationStates[data.target_lang];
                // 直接累加内容，不使用打字机效果以提高性能
                state.content += data.content;
                state.textarea.value = state.content;
                state.tokenCount = data.token_count || 0;
                
                // 更新性能指标
                if (data.tokens_per_second !== undefined && data.elapsed_time !== undefined) {
                    updatePerformanceMetrics(state, data.tokens_per_second, data.elapsed_time);
                }
                
                // 自动滚动到底部
                state.textarea.scrollTop = state.textarea.scrollHeight;
            }
            break;
            
        case 'complete':
            if (translationStates[data.target_lang]) {
                const state = translationStates[data.target_lang];
                state.completed = true;
                state.textarea.value = data.final_content;
                state.textarea.className = 'form-control translation-result translation-completed';
                state.textarea.placeholder = '翻译完成';
                state.statusIndicator.className = 'stream-status completed';
                state.statusIndicator.textContent = '完成';
                
                // 显示最终性能指标
                if (data.tokens_per_second !== undefined && data.total_time !== undefined) {
                    updatePerformanceMetrics(state, data.tokens_per_second, data.total_time, data.total_tokens, true);
                }
                
                // 存储翻译结果
                if (!currentTranslations) {
                    currentTranslations = {
                        source_text: document.getElementById('sourceText').value,
                        translations: {}
                    };
                }
                currentTranslations.translations[data.target_lang] = {
                    text: data.final_content
                };
                
                // 短暂延迟后移除状态指示器
                setTimeout(() => {
                    if (state.statusIndicator) {
                        state.statusIndicator.style.opacity = '0';
                        setTimeout(() => {
                            if (state.statusIndicator && state.statusIndicator.parentNode) {
                                state.statusIndicator.parentNode.removeChild(state.statusIndicator);
                            }
                        }, 300);
                    }
                }, 2000);
            }
            break;
            
        case 'error':
            console.error('翻译错误:', data.error);
            if (data.target_lang && translationStates[data.target_lang]) {
                const state = translationStates[data.target_lang];
                state.textarea.value = `翻译失败: ${data.error}`;
                state.textarea.className = 'form-control translation-result translation-error';
                state.statusIndicator.className = 'stream-status error';
                state.statusIndicator.textContent = '错误';
            }
            break;
            
        case 'finished':
            console.log('所有翻译完成');
            // 清理所有状态
            Object.values(translationStates).forEach(state => {
                if (state.textarea && state.completed) {
                    // 移除光标效果
                    state.textarea.className = 'form-control translation-result';
                }
            });
            break;
    }
}

// 打字机效果函数
async function typewriterEffect(element, text, clearFirst = false, speed = 30) {
    if (clearFirst) {
        element.value = '';
    }
    
    const currentValue = element.value;
    
    for (let i = 0; i < text.length; i++) {
        element.value = currentValue + text.slice(0, i + 1);
        // 自动滚动到底部
        element.scrollTop = element.scrollHeight;
        
        // 控制打字速度
        await new Promise(resolve => setTimeout(resolve, speed));
    }
}

// 状态信息打字机效果（临时显示状态信息）
async function typewriterStatusEffect(element, statusText, duration = 1500) {
    const originalValue = element.value;
    const originalPlaceholder = element.placeholder;
    
    // 设置状态文本
    element.placeholder = statusText;
    element.value = '';
    
    // 等待指定时间
    await new Promise(resolve => setTimeout(resolve, duration));
    
    // 恢复原始内容
    element.placeholder = originalPlaceholder;
    element.value = originalValue;
}

// 显示翻译结果
function displayTranslations(data) {
    const items = document.querySelectorAll('.target-lang-item');
    
    items.forEach(item => {
        const lang = item.querySelector('.target-lang-select').value;
        const resultArea = item.querySelector('.translation-result');
        const translation = data.translations[lang];
        
        if (translation) {
            resultArea.value = translation.text;
            
            // 显示性能指标
            if (translation.performance_metrics) {
                const performanceDiv = item.querySelector('.performance-metrics');
                if (performanceDiv) {
                    const tokensPerSecondSpan = performanceDiv.querySelector('.tokens-per-second');
                    const translationTimeSpan = performanceDiv.querySelector('.translation-time');
                    
                    if (tokensPerSecondSpan && translationTimeSpan) {
                        const metrics = translation.performance_metrics;
                        tokensPerSecondSpan.textContent = `${metrics.tokens_per_second} tokens/s`;
                        translationTimeSpan.textContent = `总用时: ${metrics.total_time}s`;
                        
                        if (metrics.total_tokens) {
                            tokensPerSecondSpan.textContent = `${metrics.tokens_per_second} tokens/s (${metrics.total_tokens} tokens)`;
                        }
                        
                        performanceDiv.style.display = 'block';
                    }
                }
            }
            
            // 显示相似翻译参考
            if (translation.similar_references && translation.similar_references.length > 0) {
                const similarDiv = document.createElement('div');
                similarDiv.className = 'similar-translation mt-2';
                similarDiv.innerHTML = '<strong>相似翻译参考:</strong>';
                
                translation.similar_references.forEach(ref => {
                    similarDiv.innerHTML += `<div>• ${ref.source.substring(0, 50)}... → ${ref.translation.substring(0, 50)}...</div>`;
                });
                
                const existingSimilar = item.querySelector('.similar-translation');
                if (existingSimilar) existingSimilar.remove();
                item.appendChild(similarDiv);
            }
        }
    });
    
    // 如果响应中包含使用的模型信息，可以显示
    if (data.model_used) {
        console.log('Translation completed using model:', data.model_used);
    }
}

// 添加目标语言
function addTargetLanguage() {
    const container = document.getElementById('targetLanguages');
    
    // 获取已选择的语言
    const existingLangs = [];
    document.querySelectorAll('.target-lang-select').forEach(select => {
        existingLangs.push(select.value);
    });
    
    // 所有可用语言
    const availableLangs = [
        { value: 'zh-cn', text: '中文大陆地区现代文简体' },
        { value: 'zh-tw', text: '中文港澳台地区现代文繁体' },
        { value: 'zh-classical-cn', text: '中文文言文简体' },
        { value: 'zh-classical-tw', text: '中文文言文繁体' },
        { value: 'en', text: 'English' },
        { value: 'ja', text: '日本語' },
        { value: 'ko', text: '한국어' },
        { value: 'es', text: 'Español' },
        { value: 'fr', text: 'Français' },
        { value: 'de', text: 'Deutsch' },
        { value: 'ru', text: 'Русский' },
        { value: 'ar', text: 'العربية' },
        { value: 'pt', text: 'Português' }
    ];
    
    // 找到第一个未使用的语言
    let selectedLang = null;
    for (const lang of availableLangs) {
        if (!existingLangs.includes(lang.value)) {
            selectedLang = lang.value;
            break;
        }
    }
    
    // 如果所有语言都已添加
    if (!selectedLang) {
        alert('所有语言都已添加！');
        return;
    }
    
    const newItem = document.createElement('div');
    newItem.className = 'target-lang-item mb-3';
    
    // 生成选项HTML，默认选中未使用的语言
    const optionsHtml = availableLangs.map(lang => 
        `<option value="${lang.value}" ${lang.value === selectedLang ? 'selected' : ''}>${lang.text}</option>`
    ).join('');
    
    newItem.innerHTML = `
        <div class="d-flex justify-content-between align-items-center mb-2">
            <select class="form-select form-select-sm target-lang-select" style="width: auto;" onchange="checkLanguageDuplication(this)">
                ${optionsHtml}
            </select>
            <button class="btn btn-sm btn-danger" onclick="removeTargetLanguage(this)">
                <i class="bi bi-trash"></i>
            </button>
        </div>
        <textarea class="form-control translation-result" rows="5" readonly 
                placeholder="翻译结果将显示在这里..."></textarea>
        <div class="mt-2">
            <button class="btn btn-sm btn-primary me-1" onclick="translateSingle(this)">
                <i class="bi bi-arrow-right"></i> 重新翻译
            </button>
            <button class="btn btn-sm btn-info me-1" onclick="evaluateTranslation(this)">
                <i class="bi bi-speedometer2"></i> 评估质量
            </button>
            <button class="btn btn-sm btn-secondary" onclick="copyTranslation(this)">
                <i class="bi bi-clipboard"></i> 复制
            </button>
        </div>
        <div class="performance-metrics mt-2" style="display: none;">
            <small class="text-muted d-flex justify-content-between">
                <span class="tokens-per-second"></span>
                <span class="translation-time"></span>
            </small>
        </div>
        <div class="evaluation-result mt-2"></div>
    `;
    
    container.appendChild(newItem);
}

// 检查语言重复
function checkLanguageDuplication(changedSelect) {
    const allSelects = document.querySelectorAll('.target-lang-select');
    const selectedValues = [];
    
    allSelects.forEach(select => {
        selectedValues.push(select.value);
    });
    
    // 检查是否有重复
    const hasDuplicates = selectedValues.length !== new Set(selectedValues).size;
    
    if (hasDuplicates) {
        // 找到第一个未使用的语言
        const availableLangs = ['zh-cn', 'zh-tw', 'zh-classical-cn', 'zh-classical-tw', 'en', 'ja', 'ko', 'es', 'fr', 'de', 'ru', 'ar', 'pt'];
        const otherValues = [];
        
        allSelects.forEach(select => {
            if (select !== changedSelect) {
                otherValues.push(select.value);
            }
        });
        
        for (const lang of availableLangs) {
            if (!otherValues.includes(lang)) {
                changedSelect.value = lang;
                break;
            }
        }
    }
}

// 删除目标语言
function removeTargetLanguage(btn) {
    const item = btn.closest('.target-lang-item');
    if (document.querySelectorAll('.target-lang-item').length > 1) {
        item.remove();
    } else {
        alert('至少需要保留一种目标语言');
    }
}

// 评估翻译质量
async function evaluateTranslation(btn) {
    const item = btn.closest('.target-lang-item');
    const sourceText = document.getElementById('sourceText').value;
    const translatedText = item.querySelector('.translation-result').value;
    
    if (!translatedText) {
        alert('没有翻译结果可评估');
        return;
    }
    
    const evaluationDiv = item.querySelector('.evaluation-result');
    evaluationDiv.innerHTML = '<span class="loading"></span> 正在评估...';
    
    try {
        const response = await axios.post('/api/evaluate', {
            source_text: sourceText,
            translated_text: translatedText,
            metrics: ['bleu', 'bert_score', 'rouge']
        });
        
        displayEvaluation(evaluationDiv, response.data);
        
    } catch (error) {
        evaluationDiv.innerHTML = `<span class="text-danger">评估失败: ${error.message}</span>`;
    }
}

// 显示评估结果
function displayEvaluation(div, data) {
    let html = '';
    
    if (data.overall_score !== undefined) {
        const score = data.overall_score;
        const scoreClass = score >= 80 ? 'good' : score >= 60 ? 'medium' : 'poor';
        html += `<div class="evaluation-score ${scoreClass}">综合评分: ${score.toFixed(1)}</div>`;
    }
    
    if (data.bleu && data.bleu.score !== undefined) {
        html += `<span class="evaluation-score">BLEU: ${data.bleu.score.toFixed(1)}</span>`;
    }
    
    if (data.bert_score && data.bert_score.f1 !== undefined) {
        html += `<span class="evaluation-score">BERT: ${(data.bert_score.f1 * 100).toFixed(1)}</span>`;
    }
    
    if (data.rouge && data.rouge.rougeL) {
        html += `<span class="evaluation-score">ROUGE-L: ${(data.rouge.rougeL.fmeasure * 100).toFixed(1)}</span>`;
    }
    
    if (data.warning) {
        html += `<div class="text-warning mt-2">${data.warning}</div>`;
    }
    
    div.innerHTML = html;
}

// 复制翻译
function copyTranslation(btn) {
    const item = btn.closest('.target-lang-item');
    const text = item.querySelector('.translation-result').value;
    
    navigator.clipboard.writeText(text).then(() => {
        btn.innerHTML = '<i class="bi bi-check"></i> 已复制';
        setTimeout(() => {
            btn.innerHTML = '<i class="bi bi-clipboard"></i> 复制';
        }, 2000);
    });
}

// 显示术语库模态框
function showTerminologyModal() {
    const modal = new bootstrap.Modal(document.getElementById('terminologyModal'));
    modal.show();
}

// 显示向量数据库模态框
function showVectorDBModal() {
    const modal = new bootstrap.Modal(document.getElementById('vectorDBModal'));
    modal.show();
}

// 上传术语库
async function uploadTerminology() {
    const fileInput = document.getElementById('terminologyFile');
    const file = fileInput.files[0];
    
    if (!file) {
        alert('请选择文件');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await axios.post('/api/terminology/upload', formData);
        alert(`成功导入 ${response.data.imported} 个术语`);
        fileInput.value = '';
    } catch (error) {
        alert('导入失败: ' + (error.response?.data?.error || error.message));
    }
}

// 导出术语库
async function exportTerminology() {
    const format = document.getElementById('exportFormat').value;
    
    try {
        const response = await axios.get(`/api/terminology/export?format=${format}`, {
            responseType: 'blob'
        });
        
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `terminology.${format}`);
        document.body.appendChild(link);
        link.click();
        link.remove();
        
    } catch (error) {
        alert('导出失败: ' + error.message);
    }
}

// 添加术语翻译行
function addTermTranslation() {
    const container = document.getElementById('termTranslations');
    const newRow = document.createElement('div');
    newRow.className = 'row mb-2';
    newRow.innerHTML = `
        <div class="col-3">
            <select class="form-select term-lang">
                <option value="zh">中文</option>
                <option value="en">English</option>
                <option value="ja">日本語</option>
                <option value="ko">한국어</option>
                <option value="es">Español</option>
                <option value="fr">Français</option>
                <option value="de">Deutsch</option>
                <option value="ru">Русский</option>
                <option value="ar">العربية</option>
                <option value="pt">Português</option>
            </select>
        </div>
        <div class="col-9">
            <input type="text" class="form-control term-translation" placeholder="翻译">
        </div>
    `;
    container.appendChild(newRow);
}

// 保存术语
async function saveTerm() {
    const term = document.getElementById('newTerm').value;
    if (!term) {
        alert('请输入术语');
        return;
    }
    
    const translations = {};
    document.querySelectorAll('#termTranslations .row').forEach(row => {
        const lang = row.querySelector('.term-lang').value;
        const translation = row.querySelector('.term-translation').value;
        if (translation) {
            translations[lang] = translation;
        }
    });
    
    if (Object.keys(translations).length === 0) {
        alert('请至少添加一个翻译');
        return;
    }
    
    try {
        const response = await axios.post('/api/terminology/add', {
            term: term,
            translations: translations
        });
        
        alert('术语添加成功');
        document.getElementById('newTerm').value = '';
        document.querySelectorAll('.term-translation').forEach(input => input.value = '');
        
    } catch (error) {
        alert('添加失败: ' + error.message);
    }
}

// 添加到向量数据库
async function addToVectorDB() {
    if (!currentTranslations.source_text) {
        alert('请先进行翻译');
        return;
    }
    
    const translations = {};
    for (const lang in currentTranslations.translations) {
        translations[lang] = currentTranslations.translations[lang].text;
    }
    
    try {
        const response = await axios.post('/api/vector-db/add', {
            source_text: currentTranslations.source_text,
            translations: translations
        });
        
        alert('成功添加到翻译记忆库');
        
    } catch (error) {
        alert('添加失败: ' + error.message);
    }
}

// 导出TMX
async function exportTMX() {
    try {
        const response = await axios.get('/api/vector-db/export?format=tmx', {
            responseType: 'blob'
        });
        
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', 'translation_memory.tmx');
        document.body.appendChild(link);
        link.click();
        link.remove();
        
    } catch (error) {
        alert('导出失败: ' + error.message);
    }
}

// 更新翻译按钮状态
function updateTranslationButtons() {
    const translateBtn = document.getElementById('translateBtn');
    
    if (isTranslating) {
        translateBtn.className = 'btn btn-danger btn-sm me-2';
        translateBtn.innerHTML = '<i class="bi bi-stop-circle"></i> 停止';
        translateBtn.onclick = stopTranslation;
    } else {
        translateBtn.className = 'btn btn-success btn-sm me-2';
        translateBtn.innerHTML = '<i class="bi bi-arrow-right-circle"></i> 翻译';
        translateBtn.onclick = translateText;
    }
}

// 停止翻译
function stopTranslation() {
    if (translationAbortController) {
        translationAbortController.abort();
        console.log('Translation stopped by user');
    }
}

// 单独翻译某个语言
async function translateSingle(btn) {
    const item = btn.closest('.target-lang-item');
    const targetLang = item.querySelector('.target-lang-select').value;
    const sourceText = document.getElementById('sourceText').value;
    const sourceLang = document.getElementById('sourceLang').value;
    const useVectorDB = document.getElementById('useVectorDB').checked;
    const useTerminology = document.getElementById('useTerminology').checked;
    const translationMode = document.getElementById('translationMode').value;
    const selectedModel = document.getElementById('ollamaModel').value;
    
    if (!sourceText.trim()) {
        alert('请输入要翻译的文本');
        return;
    }
    
    if (!selectedModel) {
        alert('请先选择或安装Ollama模型');
        return;
    }
    
    // 设置按钮状态
    const originalHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="loading"></span>';
    
    // 清空当前语言的翻译结果和性能指标
    const textarea = item.querySelector('.translation-result');
    const performanceDiv = item.querySelector('.performance-metrics');
    const reflectionDiv = item.querySelector('.reflection-status');
    
    textarea.value = '';
    textarea.style.backgroundColor = '#f8f9fa';
    if (performanceDiv) {
        performanceDiv.style.display = 'none';
    }
    if (reflectionDiv) {
        reflectionDiv.style.display = 'none';
    }
    
    try {
        // 根据翻译模式选择不同的翻译方法
        switch (translationMode) {
            case 'simple':
                await translateSingleTraditional(sourceText, sourceLang, [targetLang], useVectorDB, useTerminology, selectedModel, item);
                break;
            case 'streaming':
                await translateSingleStreaming(sourceText, sourceLang, [targetLang], useVectorDB, useTerminology, selectedModel, item);
                break;
            case 'reflection':
                await translateSingleReflection(sourceText, sourceLang, [targetLang], useVectorDB, useTerminology, selectedModel, 1, item);
                break;
            case 'triple':
                await translateSingleReflection(sourceText, sourceLang, [targetLang], useVectorDB, useTerminology, selectedModel, 2, item);
                break;
            case 'iterative':
                const iterativeCount = parseInt(document.getElementById('iterativeCount').value);
                await translateSingleReflection(sourceText, sourceLang, [targetLang], useVectorDB, useTerminology, selectedModel, iterativeCount, item);
                break;
            default:
                await translateSingleTraditional(sourceText, sourceLang, [targetLang], useVectorDB, useTerminology, selectedModel, item);
        }
        
    } catch (error) {
        if (error.name === 'AbortError') {
            console.log('Translation was stopped by user');
        } else {
            let errorMsg = '翻译失败: ';
            
            if (error.message.includes('Network Error') || error.message.includes('Failed to fetch')) {
                errorMsg += 'Ollama服务连接失败，请确保服务正在运行';
            } else if (error.response?.data?.error) {
                errorMsg += error.response.data.error;
            } else {
                errorMsg += error.message;
            }
            
            alert(errorMsg);
        }
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalHTML;
    }
}

// 单独语言的传统翻译
async function translateSingleTraditional(sourceText, sourceLang, targetLangs, useVectorDB, useTerminology, selectedModel, targetItem) {
    const response = await axios.post('/api/translate', {
        source_text: sourceText,
        source_lang: sourceLang,
        target_langs: targetLangs,
        use_vector_db: useVectorDB,
        use_terminology: useTerminology,
        model: selectedModel
    });
    
    // 显示翻译结果
    const targetLang = targetLangs[0];
    const translation = response.data.translations[targetLang];
    const textarea = targetItem.querySelector('.translation-result');
    
    if (translation) {
        textarea.value = translation.text;
        
        // 显示性能指标
        if (translation.performance_metrics) {
            const performanceDiv = targetItem.querySelector('.performance-metrics');
            if (performanceDiv) {
                const tokensPerSecondSpan = performanceDiv.querySelector('.tokens-per-second');
                const translationTimeSpan = performanceDiv.querySelector('.translation-time');
                
                if (tokensPerSecondSpan && translationTimeSpan) {
                    const metrics = translation.performance_metrics;
                    tokensPerSecondSpan.textContent = `${metrics.tokens_per_second} tokens/s`;
                    translationTimeSpan.textContent = `总用时: ${metrics.total_time}s`;
                    
                    if (metrics.total_tokens) {
                        tokensPerSecondSpan.textContent = `${metrics.tokens_per_second} tokens/s (${metrics.total_tokens} tokens)`;
                    }
                    
                    performanceDiv.style.display = 'block';
                }
            }
        }
        
        // 更新全局翻译结果
        if (!currentTranslations) {
            currentTranslations = {
                source_text: sourceText,
                translations: {}
            };
        }
        currentTranslations.translations[targetLang] = translation;
        
        // 显示相似翻译参考
        if (translation.similar_references && translation.similar_references.length > 0) {
            const similarDiv = document.createElement('div');
            similarDiv.className = 'similar-translation mt-2';
            similarDiv.innerHTML = '<strong>相似翻译参考:</strong>';
            
            translation.similar_references.forEach(ref => {
                similarDiv.innerHTML += `<div>• ${ref.source.substring(0, 50)}... → ${ref.translation.substring(0, 50)}...</div>`;
            });
            
            const existingSimilar = targetItem.querySelector('.similar-translation');
            if (existingSimilar) existingSimilar.remove();
            targetItem.appendChild(similarDiv);
        }
    }
}

// 单独语言的流式翻译
async function translateSingleStreaming(sourceText, sourceLang, targetLangs, useVectorDB, useTerminology, selectedModel, targetItem) {
    // 创建AbortController用于停止请求
    const singleAbortController = new AbortController();
    
    const response = await fetch('/api/translate/stream', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            source_text: sourceText,
            source_lang: sourceLang,
            target_langs: targetLangs,
            use_vector_db: useVectorDB,
            use_terminology: useTerminology,
            model: selectedModel
        }),
        signal: singleAbortController.signal
    });
    
    if (!response.ok) {
        throw new Error('翻译请求失败');
    }
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    
    const targetLang = targetLangs[0];
    const translationState = {
        content: '',
        textarea: targetItem.querySelector('.translation-result'),
        performanceDiv: targetItem.querySelector('.performance-metrics'),
        completed: false,
        startTime: null,
        tokenCount: 0
    };
    
    // 确保性能指标区域存在
    if (!translationState.performanceDiv) {
        const performanceDiv = document.createElement('div');
        performanceDiv.className = 'performance-metrics mt-2';
        performanceDiv.style.display = 'none';
        performanceDiv.innerHTML = `
            <small class="text-muted d-flex justify-content-between">
                <span class="tokens-per-second"></span>
                <span class="translation-time"></span>
            </small>
        `;
        
        // 找到合适的位置插入性能指标区域
        const buttonRow = targetItem.querySelector('.mt-2');
        if (buttonRow) {
            // 插入到按钮行之后
            buttonRow.parentNode.insertBefore(performanceDiv, buttonRow.nextSibling);
        } else {
            targetItem.appendChild(performanceDiv);
        }
        
        translationState.performanceDiv = performanceDiv;
    }
    
    // 添加状态指示器
    let statusIndicator = targetItem.querySelector('.stream-status');
    if (!statusIndicator) {
        statusIndicator = document.createElement('div');
        statusIndicator.className = 'stream-status waiting';
        statusIndicator.textContent = '等待中';
        targetItem.appendChild(statusIndicator);
    }
    translationState.statusIndicator = statusIndicator;
    
    // 设置初始状态
    translationState.textarea.className = 'form-control translation-result translation-streaming';
    translationState.textarea.placeholder = '等待翻译...';
    
    try {
        while (true) {
            const { done, value } = await reader.read();
            
            if (done) break;
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        await handleSingleStreamData(data, translationState, targetLang);
                    } catch (e) {
                        console.error('解析流数据失败:', e);
                    }
                }
            }
        }
    } finally {
        reader.releaseLock();
    }
}

// 处理单个语言的流式数据
async function handleSingleStreamData(data, state, targetLang) {
    if (data.target_lang !== targetLang) return; // 只处理目标语言的数据
    
    switch (data.type) {
        case 'start':
            console.log(`开始翻译到 ${data.target_lang}`);
            state.textarea.className = 'form-control translation-result translation-active typing-cursor';
            state.textarea.placeholder = '正在翻译中...';
            state.statusIndicator.className = 'stream-status translating';
            state.statusIndicator.textContent = '翻译中';
            state.startTime = data.start_time || Date.now() / 1000;
            break;
            
        case 'content':
            if (!state.completed) {
                state.content += data.content;
                state.textarea.value = state.content;
                state.tokenCount = data.token_count || 0;
                
                // 更新性能指标
                if (data.tokens_per_second !== undefined && data.elapsed_time !== undefined) {
                    updatePerformanceMetrics(state, data.tokens_per_second, data.elapsed_time);
                }
                
                // 自动滚动到底部
                state.textarea.scrollTop = state.textarea.scrollHeight;
            }
            break;
            
        case 'complete':
            state.completed = true;
            state.textarea.value = data.final_content;
            state.textarea.className = 'form-control translation-result translation-completed';
            state.textarea.placeholder = '翻译完成';
            state.statusIndicator.className = 'stream-status completed';
            state.statusIndicator.textContent = '完成';
            
            // 显示最终性能指标
            if (data.tokens_per_second !== undefined && data.total_time !== undefined) {
                updatePerformanceMetrics(state, data.tokens_per_second, data.total_time, data.total_tokens, true);
            }
            
            // 更新全局翻译结果
            if (!currentTranslations) {
                currentTranslations = {
                    source_text: document.getElementById('sourceText').value,
                    translations: {}
                };
            }
            currentTranslations.translations[targetLang] = {
                text: data.final_content
            };
            
            // 短暂延迟后移除状态指示器
            setTimeout(() => {
                if (state.statusIndicator) {
                    state.statusIndicator.style.opacity = '0';
                    setTimeout(() => {
                        if (state.statusIndicator && state.statusIndicator.parentNode) {
                            state.statusIndicator.parentNode.removeChild(state.statusIndicator);
                        }
                    }, 300);
                }
            }, 2000);
            break;
            
        case 'error':
            console.error('翻译错误:', data.error);
            state.textarea.value = `翻译失败: ${data.error}`;
            state.textarea.className = 'form-control translation-result translation-error';
            state.statusIndicator.className = 'stream-status error';
            state.statusIndicator.textContent = '错误';
            break;
    }
}

// 更新性能指标
function updatePerformanceMetrics(state, tokensPerSecond, elapsedTime, totalTokens = null, isFinal = false) {
    if (!state.performanceDiv) {
        console.warn('Performance div not found for state');
        return;
    }
    
    const tokensPerSecondSpan = state.performanceDiv.querySelector('.tokens-per-second');
    const translationTimeSpan = state.performanceDiv.querySelector('.translation-time');
    
    if (tokensPerSecondSpan && translationTimeSpan) {
        // 更新tokens/s显示
        tokensPerSecondSpan.textContent = `${tokensPerSecond} tokens/s`;
        
        // 更新时间显示
        if (isFinal) {
            translationTimeSpan.textContent = `总用时: ${elapsedTime}s`;
            if (totalTokens) {
                tokensPerSecondSpan.textContent = `${tokensPerSecond} tokens/s (${totalTokens} tokens)`;
            }
        } else {
            translationTimeSpan.textContent = `${elapsedTime.toFixed(1)}s`;
        }
        
        // 显示性能指标区域
        state.performanceDiv.style.display = 'block';
    } else {
        console.error('Performance spans not found in performance div');
    }
}

// 互换源语言和第一个目标语言
function swapSourceAndTarget() {
    // 检查是否正在翻译
    if (isTranslating) {
        alert('翻译进行中，请等待翻译完成后再进行互换');
        return;
    }
    
    const sourceText = document.getElementById('sourceText');
    const sourceLangSelect = document.getElementById('sourceLang');
    
    // 获取第一个目标语言区域
    const firstTargetItem = document.querySelector('.target-lang-item');
    if (!firstTargetItem) {
        alert('请先添加至少一个目标语言');
        return;
    }
    
    const firstTargetSelect = firstTargetItem.querySelector('.target-lang-select');
    const firstTargetTextarea = firstTargetItem.querySelector('.translation-result');
    
    // 检查是否有源文本
    if (!sourceText.value.trim()) {
        alert('请先输入源文本');
        return;
    }
    
    // 检查第一个目标语言是否有翻译结果
    if (!firstTargetTextarea.value.trim()) {
        alert('第一个目标语言没有翻译结果可以互换\n请先进行翻译，然后再使用互换功能');
        return;
    }
    
    // 获取当前值
    const currentSourceText = sourceText.value;
    const currentSourceLang = sourceLangSelect.value;
    const currentTargetLang = firstTargetSelect.value;
    const currentTargetText = firstTargetTextarea.value;
    
    // 确认互换操作
    const sourceLangName = getLanguageDisplayName(currentSourceLang);
    const targetLangName = getLanguageDisplayName(currentTargetLang);
    
    if (!confirm(`确定要互换源语言（${sourceLangName}）和第一个目标语言（${targetLangName}）吗？\n\n这将清空其他目标语言的翻译结果。`)) {
        return;
    }
    
    // 执行互换
    // 1. 将第一个目标语言的翻译结果设置为源文本
    sourceText.value = currentTargetText;
    
    // 2. 将第一个目标语言的语种设置为源语言
    sourceLangSelect.value = currentTargetLang;
    
    // 3. 将原来的源语言设置为第一个目标语言
    // 处理自动检测的情况
    let newTargetLang = currentSourceLang;
    if (currentSourceLang === 'auto') {
        // 如果原来是自动检测，尝试从翻译缓存中获取检测到的语言
        if (currentTranslations && currentTranslations.source_lang && currentTranslations.source_lang !== 'auto') {
            newTargetLang = currentTranslations.source_lang;
        } else {
            // 默认设为中文简体
            newTargetLang = 'zh-cn';
        }
    }
    firstTargetSelect.value = newTargetLang;
    
    // 4. 将原来的源文本设置为第一个目标语言的翻译结果
    firstTargetTextarea.value = currentSourceText;
    
    // 5. 更新字符计数
    document.getElementById('charCount').textContent = sourceText.value.length;
    
    // 6. 清空其他目标语言的翻译结果和相关状态
    const otherTargetItems = document.querySelectorAll('.target-lang-item:not(:first-child)');
    otherTargetItems.forEach(item => {
        const textarea = item.querySelector('.translation-result');
        if (textarea) {
            textarea.value = '';
            textarea.style.backgroundColor = '#f8f9fa';
            textarea.className = 'form-control translation-result'; // 重置样式类
        }
        
        // 隐藏性能指标
        const performanceDiv = item.querySelector('.performance-metrics');
        if (performanceDiv) {
            performanceDiv.style.display = 'none';
        }
        
        // 清空评估结果
        const evaluationDiv = item.querySelector('.evaluation-result');
        if (evaluationDiv) {
            evaluationDiv.innerHTML = '';
        }
        
        // 移除相似翻译参考
        const similarDiv = item.querySelector('.similar-translation');
        if (similarDiv) {
            similarDiv.remove();
        }
    });
    
    // 7. 重置第一个目标语言的状态
    firstTargetTextarea.style.backgroundColor = '#f8f9fa';
    firstTargetTextarea.className = 'form-control translation-result';
    
    // 隐藏第一个目标语言的性能指标
    const firstPerformanceDiv = firstTargetItem.querySelector('.performance-metrics');
    if (firstPerformanceDiv) {
        firstPerformanceDiv.style.display = 'none';
    }
    
    // 清空第一个目标语言的评估结果
    const firstEvaluationDiv = firstTargetItem.querySelector('.evaluation-result');
    if (firstEvaluationDiv) {
        firstEvaluationDiv.innerHTML = '';
    }
    
    // 8. 检查语言重复并自动调整
    checkLanguageDuplication(firstTargetSelect);
    
    // 9. 清空当前翻译缓存
    currentTranslations = {};
    
    console.log(`语言和内容互换完成: ${sourceLangName} ↔ ${targetLangName}`);
    
    // 10. 显示成功提示
    showSwapSuccess(sourceLangName, targetLangName);
}

// 获取语言显示名称
function getLanguageDisplayName(langCode) {
    const languageNames = {
        'auto': '自动检测',
        'zh-cn': '中文大陆地区现代文简体',
        'zh-tw': '中文港澳台地区现代文繁体',
        'zh-classical-cn': '中文文言文简体',
        'zh-classical-tw': '中文文言文繁体',
        'en': 'English',
        'ja': '日本語',
        'ko': '한국어',
        'es': 'Español',
        'fr': 'Français',
        'de': 'Deutsch',
        'ru': 'Русский',
        'ar': 'العربية',
        'pt': 'Português'
    };
    return languageNames[langCode] || langCode;
}

// HTML转义函数
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 显示互换成功提示
function showSwapSuccess(sourceLang, targetLang) {
    const swapBtn = document.getElementById('swapBtn');
    const originalHTML = swapBtn.innerHTML;
    
    swapBtn.innerHTML = '<i class="bi bi-check"></i> 已互换';
    swapBtn.className = 'btn btn-success btn-sm';
    
    setTimeout(() => {
        swapBtn.innerHTML = originalHTML;
        swapBtn.className = 'btn btn-outline-secondary btn-sm';
    }, 2000);
}

// 反思翻译函数
async function translateTextReflection(sourceText, sourceLang, targetLangs, useVectorDB, useTerminology, selectedModel, reflectionRounds) {
    // 初始化全局翻译结果对象
    currentTranslations = {
        source_text: sourceText,
        source_lang: sourceLang,
        translations: {},
        model_used: selectedModel
    };
    
    // 存储每种语言的翻译状态
    const translationStates = {};
    targetLangs.forEach(lang => {
        translationStates[lang] = {
            currentTranslation: '',
            reflections: [],
            improvements: [],
            textarea: null,
            container: null,
            statusDiv: null
        };
    });
    
    // 获取对应的UI元素
    document.querySelectorAll('.target-lang-item').forEach((item, index) => {
        const lang = item.querySelector('.target-lang-select').value;
        if (targetLangs.includes(lang)) {
            translationStates[lang].textarea = item.querySelector('.translation-result');
            translationStates[lang].container = item;
            
            // 添加状态显示区域
            let statusDiv = item.querySelector('.reflection-status');
            if (!statusDiv) {
                statusDiv = document.createElement('div');
                statusDiv.className = 'reflection-status mt-2 p-2 bg-light border rounded';
                statusDiv.style.fontSize = '0.85rem';
                
                // 插入到性能指标之前
                const performanceDiv = item.querySelector('.performance-metrics');
                if (performanceDiv) {
                    item.insertBefore(statusDiv, performanceDiv);
                } else {
                    item.appendChild(statusDiv);
                }
            }
            translationStates[lang].statusDiv = statusDiv;
            
            // 设置初始状态
            translationStates[lang].textarea.className = 'form-control translation-result translation-active';
            translationStates[lang].statusDiv.innerHTML = '<i class="bi bi-hourglass-split"></i> 准备开始反思翻译...';
        }
    });
    
    // 对每个目标语言进行反思翻译
    for (const targetLang of targetLangs) {
        const state = translationStates[targetLang];
        
        try {
            // 第一步：初始翻译
            state.statusDiv.innerHTML = '<i class="bi bi-translate"></i> 正在进行初始翻译...';
            await typewriterStatusEffect(state.textarea, '正在进行初始翻译...');
            
            const initialTranslation = await performSingleTranslation(
                sourceText, sourceLang, targetLang, useVectorDB, useTerminology, selectedModel
            );
            
            state.currentTranslation = initialTranslation;
            await typewriterEffect(state.textarea, initialTranslation, true, 20);
            state.statusDiv.innerHTML = '<i class="bi bi-check-circle text-success"></i> 初始翻译完成';
            
            // 进行反思和优化轮次
            for (let round = 1; round <= reflectionRounds; round++) {
                state.statusDiv.innerHTML = `<i class="bi bi-lightbulb"></i> 第${round}轮反思中...`;
                await typewriterStatusEffect(state.textarea, `第${round}轮反思分析中...`);
                
                // 反思阶段
                const reflectionResult = await performReflection(
                    sourceText, state.currentTranslation, sourceLang, targetLang, selectedModel
                );
                state.reflections.push(reflectionResult.reflection);
                
                state.statusDiv.innerHTML = `<i class="bi bi-gear"></i> 第${round}轮优化中...`;
                await typewriterStatusEffect(state.textarea, `第${round}轮优化改进中...`);
                
                // 优化阶段
                const improvementResult = await performImprovement(
                    sourceText, state.currentTranslation, reflectionResult.reflection, sourceLang, targetLang, selectedModel
                );
                
                state.currentTranslation = improvementResult.improved_translation;
                state.improvements.push(improvementResult.improved_translation);
                await typewriterEffect(state.textarea, improvementResult.improved_translation, true, 15);
                
                state.statusDiv.innerHTML = `<i class="bi bi-check-circle text-success"></i> 第${round}轮优化完成`;
                
                // 短暂延迟以显示进度
                await new Promise(resolve => setTimeout(resolve, 800));
            }
            
            // 最终状态
            state.textarea.className = 'form-control translation-result translation-completed';
            state.statusDiv.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <span><i class="bi bi-star text-warning"></i> 反思翻译完成 (${reflectionRounds}轮优化)</span>
                    <button class="btn btn-sm btn-outline-info" onclick="showReflectionDetails('${targetLang}')">
                        <i class="bi bi-eye"></i> 查看详情
                    </button>
                </div>
            `;
            
            // 显示累计性能指标（如果有的话）
            const performanceDiv = state.container.querySelector('.performance-metrics');
            if (performanceDiv) {
                            // 计算总的性能指标（简单估算）
            const totalTokens = state.currentTranslation.split(' ').length + Math.floor(state.currentTranslation.length / 4);
                const estimatedTime = reflectionRounds * 3 + 2; // 估算总时间
                const avgTokensPerSecond = totalTokens / estimatedTime;
                
                const tokensPerSecondSpan = performanceDiv.querySelector('.tokens-per-second');
                const translationTimeSpan = performanceDiv.querySelector('.translation-time');
                
                if (tokensPerSecondSpan && translationTimeSpan) {
                    tokensPerSecondSpan.textContent = `平均 ${avgTokensPerSecond.toFixed(1)} tokens/s`;
                    translationTimeSpan.textContent = `总用时: ~${estimatedTime}s (${reflectionRounds}轮)`;
                    performanceDiv.style.display = 'block';
                }
            }
            
            // 存储翻译结果
            currentTranslations.translations[targetLang] = {
                text: state.currentTranslation,
                reflections: state.reflections,
                improvements: state.improvements,
                mode: 'reflection'
            };
            
        } catch (error) {
            console.error(`反思翻译失败 (${targetLang}):`, error);
            state.textarea.value = `反思翻译失败: ${error.message}`;
            state.textarea.className = 'form-control translation-result translation-error';
            state.statusDiv.innerHTML = '<i class="bi bi-exclamation-triangle text-danger"></i> 翻译失败';
        }
    }
}

// 执行单次翻译
async function performSingleTranslation(sourceText, sourceLang, targetLang, useVectorDB, useTerminology, selectedModel) {
    const response = await axios.post('/api/translate', {
        source_text: sourceText,
        source_lang: sourceLang,
        target_langs: [targetLang],
        use_vector_db: useVectorDB,
        use_terminology: useTerminology,
        model: selectedModel
    });
    
    return response.data.translations[targetLang].text;
}

// 执行反思
async function performReflection(sourceText, translation, sourceLang, targetLang, selectedModel) {
    const response = await axios.post('/api/translate/reflect', {
        source_text: sourceText,
        translation: translation,
        source_lang: sourceLang,
        target_lang: targetLang,
        model: selectedModel
    });
    
    return {
        reflection: response.data.reflection,
        metrics: response.data.metrics
    };
}

// 执行改进
async function performImprovement(sourceText, currentTranslation, reflection, sourceLang, targetLang, selectedModel) {
    const response = await axios.post('/api/translate/improve', {
        source_text: sourceText,
        current_translation: currentTranslation,
        reflection: reflection,
        source_lang: sourceLang,
        target_lang: targetLang,
        model: selectedModel
    });
    
    return {
        improved_translation: response.data.improved_translation,
        metrics: response.data.metrics
    };
}

// 显示反思详情
function showReflectionDetails(targetLang) {
    const translation = currentTranslations?.translations[targetLang];
    if (!translation || !translation.reflections) {
        alert('没有找到反思详情');
        return;
    }
    
    let detailsHtml = `
        <div class="modal fade" id="reflectionDetailsModal" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">反思翻译详情 - ${getLanguageDisplayName(targetLang)}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="accordion" id="reflectionAccordion">
    `;
    
    // 显示每一轮的反思和改进
    translation.reflections.forEach((reflection, index) => {
        const improvement = translation.improvements[index];
        detailsHtml += `
            <div class="accordion-item">
                <h2 class="accordion-header">
                    <button class="accordion-button ${index === 0 ? '' : 'collapsed'}" type="button" 
                            data-bs-toggle="collapse" data-bs-target="#collapse${index}">
                        第${index + 1}轮反思与优化
                    </button>
                </h2>
                <div id="collapse${index}" class="accordion-collapse collapse ${index === 0 ? 'show' : ''}" 
                     data-bs-parent="#reflectionAccordion">
                    <div class="accordion-body">
                        <h6><i class="bi bi-lightbulb"></i> 反思意见：</h6>
                        <div class="bg-light p-2 rounded mb-3">${escapeHtml(reflection)}</div>
                        <h6><i class="bi bi-arrow-up-circle"></i> 优化结果：</h6>
                        <div class="bg-success bg-opacity-10 p-2 rounded">${escapeHtml(improvement)}</div>
                    </div>
                </div>
            </div>
        `;
    });
    
    detailsHtml += `
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // 移除现有模态框
    const existingModal = document.getElementById('reflectionDetailsModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // 添加新模态框
    document.body.insertAdjacentHTML('beforeend', detailsHtml);
    
    // 显示模态框
    const modal = new bootstrap.Modal(document.getElementById('reflectionDetailsModal'));
    modal.show();
}

// 单独语言的反思翻译
async function translateSingleReflection(sourceText, sourceLang, targetLangs, useVectorDB, useTerminology, selectedModel, reflectionRounds, targetItem) {
    const targetLang = targetLangs[0];
    const textarea = targetItem.querySelector('.translation-result');
    
    // 初始化全局翻译结果对象（如果不存在）
    if (!currentTranslations) {
        currentTranslations = {
            source_text: sourceText,
            source_lang: sourceLang,
            translations: {},
            model_used: selectedModel
        };
    }
    
    // 添加状态显示区域
    let statusDiv = targetItem.querySelector('.reflection-status');
    if (!statusDiv) {
        statusDiv = document.createElement('div');
        statusDiv.className = 'reflection-status mt-2 p-2 bg-light border rounded';
        statusDiv.style.fontSize = '0.85rem';
        
        // 插入到性能指标之前
        const performanceDiv = targetItem.querySelector('.performance-metrics');
        if (performanceDiv) {
            targetItem.insertBefore(statusDiv, performanceDiv);
        } else {
            targetItem.appendChild(statusDiv);
        }
    }
    statusDiv.style.display = 'block';
    
    const translationState = {
        currentTranslation: '',
        reflections: [],
        improvements: []
    };
    
    try {
        // 设置初始状态
        textarea.className = 'form-control translation-result translation-active';
        statusDiv.innerHTML = '<i class="bi bi-hourglass-split"></i> 准备开始反思翻译...';
        
        // 第一步：初始翻译
        statusDiv.innerHTML = '<i class="bi bi-translate"></i> 正在进行初始翻译...';
        await typewriterStatusEffect(textarea, '正在进行初始翻译...');
        
        const initialTranslation = await performSingleTranslation(
            sourceText, sourceLang, targetLang, useVectorDB, useTerminology, selectedModel
        );
        
        translationState.currentTranslation = initialTranslation;
        await typewriterEffect(textarea, initialTranslation, true, 20);
        statusDiv.innerHTML = '<i class="bi bi-check-circle text-success"></i> 初始翻译完成';
        
        // 进行反思和优化轮次
        for (let round = 1; round <= reflectionRounds; round++) {
            statusDiv.innerHTML = `<i class="bi bi-lightbulb"></i> 第${round}轮反思中...`;
            await typewriterStatusEffect(textarea, `第${round}轮反思分析中...`);
            
            // 反思阶段
            const reflectionResult = await performReflection(
                sourceText, translationState.currentTranslation, sourceLang, targetLang, selectedModel
            );
            translationState.reflections.push(reflectionResult.reflection);
            
            statusDiv.innerHTML = `<i class="bi bi-gear"></i> 第${round}轮优化中...`;
            await typewriterStatusEffect(textarea, `第${round}轮优化改进中...`);
            
            // 优化阶段
            const improvementResult = await performImprovement(
                sourceText, translationState.currentTranslation, reflectionResult.reflection, sourceLang, targetLang, selectedModel
            );
            
            translationState.currentTranslation = improvementResult.improved_translation;
            translationState.improvements.push(improvementResult.improved_translation);
            await typewriterEffect(textarea, improvementResult.improved_translation, true, 15);
            
            statusDiv.innerHTML = `<i class="bi bi-check-circle text-success"></i> 第${round}轮优化完成`;
            
            // 短暂延迟以显示进度
            await new Promise(resolve => setTimeout(resolve, 800));
        }
        
        // 最终状态
        textarea.className = 'form-control translation-result translation-completed';
        statusDiv.innerHTML = `
            <div class="d-flex justify-content-between align-items-center">
                <span><i class="bi bi-star text-warning"></i> 反思翻译完成 (${reflectionRounds}轮优化)</span>
                <button class="btn btn-sm btn-outline-info" onclick="showSingleReflectionDetails('${targetLang}', ${JSON.stringify(translationState).replace(/"/g, '&quot;')})">
                    <i class="bi bi-eye"></i> 查看详情
                </button>
            </div>
        `;
        
        // 显示累计性能指标
        const performanceDiv = targetItem.querySelector('.performance-metrics');
        if (performanceDiv) {
            // 计算总的性能指标（简单估算）
            const totalTokens = translationState.currentTranslation.split(' ').length + Math.floor(translationState.currentTranslation.length / 4);
            const estimatedTime = reflectionRounds * 3 + 2; // 估算总时间
            const avgTokensPerSecond = totalTokens / estimatedTime;
            
            const tokensPerSecondSpan = performanceDiv.querySelector('.tokens-per-second');
            const translationTimeSpan = performanceDiv.querySelector('.translation-time');
            
            if (tokensPerSecondSpan && translationTimeSpan) {
                tokensPerSecondSpan.textContent = `平均 ${avgTokensPerSecond.toFixed(1)} tokens/s`;
                translationTimeSpan.textContent = `总用时: ~${estimatedTime}s (${reflectionRounds}轮)`;
                performanceDiv.style.display = 'block';
            }
        }
        
        // 更新全局翻译结果
        currentTranslations.translations[targetLang] = {
            text: translationState.currentTranslation,
            reflections: translationState.reflections,
            improvements: translationState.improvements,
            mode: 'reflection'
        };
        
    } catch (error) {
        console.error(`单独反思翻译失败 (${targetLang}):`, error);
        textarea.value = `反思翻译失败: ${error.message}`;
        textarea.className = 'form-control translation-result translation-error';
        statusDiv.innerHTML = '<i class="bi bi-exclamation-triangle text-danger"></i> 翻译失败';
    }
}

// 显示单独反思详情（简化版本，直接使用传入的数据）
function showSingleReflectionDetails(targetLang, translationState) {
    // 使用全局的currentTranslations数据
    const translation = currentTranslations?.translations[targetLang];
    if (!translation || !translation.reflections) {
        alert('没有找到反思详情');
        return;
    }
    
    showReflectionDetails(targetLang);
} 