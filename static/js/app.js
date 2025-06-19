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
    
    // 加载可用的Ollama模型
    loadAvailableModels();
});

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
    const useStreaming = document.getElementById('useStreaming').checked;
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
        if (useStreaming) {
            // 使用流式翻译
            await translateTextStreaming(sourceText, sourceLang, targetLangs, useVectorDB, useTerminology, selectedModel);
        } else {
            // 使用传统翻译
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

// 显示翻译结果
function displayTranslations(data) {
    const items = document.querySelectorAll('.target-lang-item');
    
    items.forEach(item => {
        const lang = item.querySelector('.target-lang-select').value;
        const resultArea = item.querySelector('.translation-result');
        const translation = data.translations[lang];
        
        if (translation) {
            resultArea.value = translation.text;
            
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
    const stopBtn = document.getElementById('stopBtn');
    
    if (isTranslating) {
        translateBtn.disabled = true;
        translateBtn.innerHTML = '<span class="loading"></span>';
        stopBtn.style.display = 'block';
    } else {
        translateBtn.disabled = false;
        translateBtn.innerHTML = '<i class="bi bi-arrow-right-circle"></i><br>翻译';
        stopBtn.style.display = 'none';
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
    const useStreaming = document.getElementById('useStreaming').checked;
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
    textarea.value = '';
    textarea.style.backgroundColor = '#f8f9fa';
    if (performanceDiv) {
        performanceDiv.style.display = 'none';
    }
    
    try {
        if (useStreaming) {
            // 使用流式翻译单个语言
            await translateSingleStreaming(sourceText, sourceLang, [targetLang], useVectorDB, useTerminology, selectedModel, item);
        } else {
            // 使用传统翻译单个语言
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