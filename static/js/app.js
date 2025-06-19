// 全局变量
let currentTranslations = {};
let defaultModel = 'qwen3:0.6b';

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
    
    // 显示加载状态
    const btn = document.getElementById('translateBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="loading"></span>';
    
    try {
        const response = await axios.post('/api/translate', {
            source_text: sourceText,
            source_lang: sourceLang,
            target_langs: targetLangs,
            use_vector_db: useVectorDB,
            use_terminology: useTerminology,
            model: selectedModel  // 传递选中的模型
        });
        
        currentTranslations = response.data;
        displayTranslations(response.data);
        
    } catch (error) {
        let errorMsg = '翻译失败: ';
        
        if (error.response?.data?.error) {
            errorMsg += error.response.data.error;
        } else if (error.code === 'ERR_NETWORK') {
            errorMsg += 'Ollama服务连接失败，请确保服务正在运行';
        } else {
            errorMsg += error.message;
        }
        
        alert(errorMsg);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-arrow-right-circle"></i><br>翻译';
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
    const newItem = document.createElement('div');
    newItem.className = 'target-lang-item mb-3';
    newItem.innerHTML = `
        <div class="d-flex justify-content-between align-items-center mb-2">
            <select class="form-select form-select-sm target-lang-select" style="width: auto;">
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
            <button class="btn btn-sm btn-danger" onclick="removeTargetLanguage(this)">
                <i class="bi bi-trash"></i>
            </button>
        </div>
        <textarea class="form-control translation-result" rows="5" readonly 
                placeholder="翻译结果将显示在这里..."></textarea>
        <div class="mt-2">
            <button class="btn btn-sm btn-info" onclick="evaluateTranslation(this)">
                <i class="bi bi-speedometer2"></i> 评估质量
            </button>
            <button class="btn btn-sm btn-secondary" onclick="copyTranslation(this)">
                <i class="bi bi-clipboard"></i> 复制
            </button>
        </div>
        <div class="evaluation-result mt-2"></div>
    `;
    
    container.appendChild(newItem);
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