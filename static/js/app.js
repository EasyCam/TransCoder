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
    document.getElementById('charCount').textContent = sourceText.value.length;
    
    // 监听翻译模式变化
    const translationModeSelect = document.getElementById('translationMode');
    translationModeSelect.addEventListener('change', function() {
        toggleIterativeCountContainer();
        track('mode.change', { mode: this.value });
    });

    // 端点切换 → 联动模型列表
    const endpointSelect = document.getElementById('endpointSelect');
    if (endpointSelect) {
        endpointSelect.addEventListener('change', function () {
            loadAvailableModels();
            track('endpoint.change', { endpoint: this.value });
        });
    }
    const langSel = document.querySelector('.lang-select');
    if (langSel) {
        langSel.addEventListener('change', function () {
            if (window.TC_I18N) TC_I18N.setLang(this.value);
            updateTranslationButtons();
            track('ui.lang', { lang: this.value });
        });
    }
    const reviewerEndpointSelect = document.getElementById('reviewerEndpointSelect');
    if (reviewerEndpointSelect) {
        reviewerEndpointSelect.addEventListener('change', function () {
            loadReviewerModels();
            track('reviewer.change', { endpoint: this.value });
        });
    }

    // 加载接入端点与模型（端点列表来自 /api/endpoints，密钥不出服务端）
    loadEndpoints();

    // 记忆库徽标 + 检索回车
    loadTMStats();
    const tmQuery = document.getElementById('tmQuery');
    if (tmQuery) tmQuery.addEventListener('keydown', e => { if (e.key === 'Enter') searchTM(); });
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

// 加载接入端点（导航栏端点框 + team 翻译/评审端点框共用一次请求）
let _endpointsCache = null;
function _fillEndpointSelect(sel, endpoints, placeholder) {
    if (!sel) return;
    sel.innerHTML = '';
    if (placeholder) {
        const none = document.createElement('option');
        none.value = '';
        none.textContent = placeholder;
        sel.appendChild(none);
    }
    endpoints.forEach(ep => {
        const opt = document.createElement('option');
        opt.value = ep.name;
        opt.textContent = `${ep.name} · ${ep.source}`;
        sel.appendChild(opt);
    });
}
async function loadEndpoints() {
    try {
        const response = await axios.get('/api/endpoints');
        const endpoints = response.data.endpoints || [];
        _endpointsCache = endpoints;
        const mainSel = document.getElementById('endpointSelect');
        const revSel = document.getElementById('reviewerEndpointSelect');
        const prevMain = mainSel ? mainSel.value : '';
        const prevRev = revSel ? revSel.value : '';
        _fillEndpointSelect(mainSel, endpoints, null);
        if (mainSel) {
            const online = endpoints.find(ep => ep.name === 'deepseek')
                || endpoints.find(ep => ep.name === 'ollama-local')
                || endpoints.find(ep => ep.source !== 'local-transformers')
                || endpoints[0];
            const keep = prevMain && endpoints.some(ep => ep.name === prevMain);
            if (keep) mainSel.value = prevMain;
            else if (online) mainSel.value = online.name;
        }
        if (revSel) {
            _fillEndpointSelect(revSel, endpoints, null);
            const prefer = prevRev && endpoints.some(ep => ep.name === prevRev)
                ? prevRev
                : (endpoints.some(ep => ep.name === 'deepseek') ? 'deepseek' : (endpoints[0] || {}).name);
            if (prefer) revSel.value = prefer;
        }
        renderEndpointManager(endpoints);
        loadAvailableModels();
        loadReviewerModels();
        return endpoints;
    } catch (e) {
        console.error('Failed to load endpoints:', e);
        const sel = document.getElementById('endpointSelect');
        if (sel) sel.innerHTML = '<option value="">端点加载失败</option>';
        return [];
    }
}
function currentEndpoint() {
    const sel = document.getElementById('endpointSelect');
    return (sel && sel.value) || null;
}

function currentReviewerEndpoint() {
    const sel = document.getElementById('reviewerEndpointSelect');
    return (sel && sel.value) || currentEndpoint();
}

function currentReviewerModel() {
    const sel = document.getElementById('reviewerModelSelect');
    return (sel && sel.value) || null;
}

// team 模式翻译：逐目标语言调用 /api/translate/team
async function translateTextTeam(sourceText, sourceLang, targetLangs, useVectorDB, useTerminology, selectedModel) {
    const reviewerEndpoint = currentReviewerEndpoint();
    const reviewerModel = currentReviewerModel();
    const teamRounds = parseInt((document.getElementById('teamRounds') || {}).value || '3');

    for (const targetLang of targetLangs) {
        const targetItem = Array.from(document.querySelectorAll('#translateWorkspace .target-lang-item')).find(
            el => el.querySelector('.target-lang-select').value === targetLang
        ) || document.querySelector('#translateWorkspace .target-lang-item');
        const textarea = targetItem ? targetItem.querySelector('.translation-result') : null;
        if (textarea) textarea.value = '（team 运行中…）';

        try {
            const payload = {
                source_text: sourceText,
                source_lang: sourceLang,
                target_lang: targetLang,
                translator_endpoint: currentEndpoint() || 'ollama-local',
                translator_model: selectedModel || undefined,
                reviewer_endpoint: reviewerEndpoint || undefined,
                reviewer_model: reviewerModel || undefined,
                review_strategy: (document.getElementById('reviewStrategy') || {}).value || 'auto',
                reviewer_fallback_endpoint: 'edge-local',
                reviewer_fallback_model: 'gemma3:270m',
                team_rounds: teamRounds,
                use_terminology: useTerminology,
                use_vector_db: useVectorDB
            };
            const resp = await axios.post('/api/translate/team', payload);
            const team = resp.data.team || {};
            if (textarea) textarea.value = team.final_translation || '';
            renderTeamReviewCards(targetItem, team);
            showTeamDegradedBanner(team);
        } catch (error) {
            const msg = (error.response && error.response.data && error.response.data.error) || error.message;
            if (textarea) textarea.value = `（team 失败：${msg}）`;
            throw error;
        }
    }
}

// 评审意见卡片（Reviewer issues 逐条）
function renderTeamReviewCards(targetItem, team) {
    const container = targetItem ? targetItem.querySelector('.team-review-cards') : null;
    if (!container) return;
    container.innerHTML = '';
    const rounds = team.rounds || [];
    rounds.forEach(r => {
        const rev = r.review || {};
        const scores = rev.scores || {};
        const issues = rev.issues || [];
        const card = document.createElement('div');
        card.className = 'card mt-2';
        card.style.fontSize = '0.83em';
        const scoreTags = Object.entries(scores).map(([k, v]) =>
            `<span class="badge bg-secondary">${k}: ${v}</span>`).join(' ');
        const issueRows = issues.map(i =>
            `<li class="list-group-item py-1"><span class="badge bg-warning text-dark">${i.type}</span> ` +
            `<code>${(i.span || '').substring(0, 60)}</code> → ${(i.advice || '')}</li>`).join('');
        card.innerHTML =
            `<div class="card-header py-1 d-flex justify-content-between">
                <span>评审 第${r.round}轮</span>
                <span class="badge ${rev.passed ? 'bg-dark' : 'bg-secondary'}">${rev.passed ? '通过' : '需修改'}</span>
            </div>` +
            `<div class="card-body py-1">${scoreTags || '<span class="text-muted">无评分</span>'}` +
            (issues.length ? `<ul class="list-group list-group-flush mt-1">${issueRows}</ul>`
                           : '<div class="text-muted ms-1">' + t('noIssues') + '</div>') +
            `</div>`;
        container.appendChild(card);
    });
}

// 降级黄条
function showTeamDegradedBanner(team) {
    const banner = document.getElementById('teamDegradedBanner');
    const text = document.getElementById('teamDegradedText');
    if (!banner) return;
    if (team && team.degraded) {
        text.textContent = `已降级：${team.degraded_reason || '评审端点不可用'} → 本地自我反思机制`;
        banner.style.display = 'block';
    } else {
        banner.style.display = 'none';
    }
}

// 加载当前所选端点的模型列表（在线拉取，失败退回配置列表）
async function _loadModelsInto(epSelectId, modelSelectId, badgeId) {
    const select = document.getElementById(modelSelectId);
    const badge = document.getElementById(badgeId);
    const epSel = document.getElementById(epSelectId);
    if (!select) return;
    const ep = (epSel && epSel.value) || null;

    try {
        select.innerHTML = '<option value="">' + t('modelLoading') + '</option>';
        select.disabled = true;
        if (badge) { badge.textContent = '…'; badge.className = 'badge bg-light text-dark'; }

        const response = await axios.get('/api/models', { params: { endpoint: ep || undefined } });
        const models = response.data.models || [];
        defaultModel = response.data.default || '';

        select.innerHTML = '';
        select.disabled = false;

        // 空值 = 用端点默认模型
        const defOpt = document.createElement('option');
        defOpt.value = '';
        defOpt.textContent = t('endpointDefault');
        select.appendChild(defOpt);
        models.forEach(model => {
            const option = document.createElement('option');
            option.value = model;
            option.textContent = model;
            if (model === defaultModel) option.selected = true;
            select.appendChild(option);
        });

        if (badge) {
            const live = !!response.data.live;
            badge.textContent = live ? t('online') : t('offline');
            badge.className = 'badge ' + (live ? 'bg-success' : 'bg-secondary');
            badge.title = response.data.note || `端点 ${ep} 的 GET /models 实时结果`;
        }
    } catch (error) {
        console.error('Failed to load models:', error);
        select.innerHTML = '<option value="">' + t('modelUnavailable') + '</option>';
        select.disabled = false;
        if (badge) { badge.textContent = t('hostUnreachable'); badge.className = 'badge bg-secondary'; }
    }
}

function loadAvailableModels() {
    return _loadModelsInto('endpointSelect', 'ollamaModel', 'endpointStatus');
}

function loadReviewerModels() {
    return _loadModelsInto('reviewerEndpointSelect', 'reviewerModelSelect', 'reviewerEndpointStatus');
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
        alert(t('enterSource'));
        return;
    }

    // 获取所有目标语言
    const targetLangs = [];
    document.querySelectorAll('#translateWorkspace .target-lang-select').forEach(select => {
        targetLangs.push(select.value);
    });
    
    if (targetLangs.length === 0) {
        alert('请至少选择一种目标语言');
        return;
    }
    
    // 设置翻译状态
    isTranslating = true;
    updateTranslationButtons();
    const _t0 = Date.now();
    let _trackOk = true;
    track('translate.start', {
        mode: translationMode, endpoint: currentEndpoint(),
        model: selectedModel || null, target_langs: targetLangs,
    });
    
    // 清空之前的翻译结果和性能指标
    document.querySelectorAll('#translateWorkspace .translation-result').forEach(textarea => {
        textarea.value = '';
        textarea.style.backgroundColor = '';
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
            case 'team':
                document.querySelectorAll('.team-review-cards').forEach(d => d.innerHTML = '');
                await translateTextTeam(sourceText, sourceLang, targetLangs, useVectorDB, useTerminology, selectedModel);
                break;
            default:
                await translateTextTraditional(sourceText, sourceLang, targetLangs, useVectorDB, useTerminology, selectedModel);
        }
        
    } catch (error) {
        _trackOk = false;
        if (error.name === 'AbortError') {
            console.log('Translation was stopped by user');
        } else {
            let errorMsg = '翻译失败: ';
            
            if (error.message.includes('Network Error') || error.message.includes('Failed to fetch')) {
                errorMsg += t('endpointDown');
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
        if (_trackOk) { captureTranslationRecord(translationMode); saveWorkspaceState(); }
        track('translate.done', {
            mode: translationMode, endpoint: currentEndpoint(),
            ok: _trackOk, ms: Date.now() - _t0, target_langs: targetLangs,
        });
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
        model: selectedModel,
        endpoint: currentEndpoint()
    });
    
    currentTranslations = response.data;
    displayTranslations(response.data.data);
    if (response.data.data && response.data.data.memory) loadTMStats();
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
            model: selectedModel,
            endpoint: currentEndpoint()
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
    document.querySelectorAll('#translateWorkspace .target-lang-item').forEach((item, index) => {
        const _sel = item.querySelector('.target-lang-select');
        if (!_sel) return;
        const lang = _sel.value;
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
            
        case 'error':
            if (data.target_lang && translationStates[data.target_lang]) {
                const st = translationStates[data.target_lang];
                st.textarea.value = (st.content || '') + (data.error ? '\n' + data.error : '');
                st.textarea.className = 'form-control translation-result translation-error';
                if (st.statusIndicator) {
                    st.statusIndicator.className = 'stream-status';
                    st.statusIndicator.textContent = '失败';
                }
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
                state.textarea.value = `${t('translationFailed')}: ${data.error}`;
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
    const items = document.querySelectorAll('#translateWorkspace .target-lang-item');
    
    items.forEach(item => {
        const sel = item.querySelector('.target-lang-select');
        const resultArea = item.querySelector('.translation-result');
        if (!sel || !resultArea) return;
        const lang = sel.value;
        const translation = (data.translations || {})[lang];
        
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
    document.querySelectorAll('#translateWorkspace .target-lang-select').forEach(select => {
        existingLangs.push(select.value);
    });
    
    // 所有可用语言
    const availableLangs = [
        { value: 'zh-cn', text: '简体中文' },
        { value: 'zh-tw', text: '繁体中文' },
        { value: 'en', text: 'English' },
        { value: 'ja', text: '日本語' },
        { value: 'ko', text: '한국어' },
        { value: 'es', text: 'Español' },
        { value: 'fr', text: 'Français' },
        { value: 'de', text: 'Deutsch' },
        { value: 'it', text: 'Italiano' },
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
        alert(t('allLangsAdded'));
        return;
    }
    
    const newItem = document.createElement('div');
    newItem.className = 'target-lang-item';

    // 生成选项HTML，默认选中未使用的语言
    const optionsHtml = availableLangs.map(lang => 
        `<option value="${lang.value}" ${lang.value === selectedLang ? 'selected' : ''}>${lang.text}</option>`
    ).join('');

    newItem.innerHTML = `
        <div class="d-flex justify-content-between align-items-center gap-2 mb-1">
            <select class="form-select form-select-sm target-lang-select" style="width: auto;" onchange="checkLanguageDuplication(this)">
                ${optionsHtml}
            </select>
            <button class="btn btn-sm btn-outline-danger" onclick="removeTargetLanguage(this)">删除</button>
        </div>
        <textarea class="form-control translation-result" placeholder="译文（AI 生成或人工输入）"></textarea>
        <div class="d-flex gap-2 flex-wrap mt-1 align-items-center">
            <button class="btn btn-sm btn-primary" onclick="translateSingle(this)">AI 翻译</button>
            <button class="btn btn-sm btn-outline-success" onclick="quickScore(this)">快速评分</button>
            <button class="btn btn-sm btn-outline-primary" onclick="gradeLanguage(this)">评分</button>
            <button class="btn btn-sm btn-outline-primary" onclick="polishLanguage(this)">润色纠错</button>
            <button class="btn btn-sm btn-outline-secondary" onclick="beginAnnotation(this)">标注</button>
            <button class="btn btn-sm btn-outline-secondary" onclick="autoAlign(this)">自动对应</button>
            <button class="btn btn-sm btn-outline-secondary" onclick="copyTranslation(this)">复制</button>
            <span class="submission-hint muted small"></span>
        </div>
        <div class="quick-result mt-1"></div>
        <div class="align-preview-src align-preview"></div>
        <div class="align-preview-tgt align-preview"></div>
        <div class="align-pairs mt-1"></div>
        <div class="annotation-form mt-1" style="display:none;">
            <div class="d-flex gap-2 align-items-center flex-wrap">
                <span class="annotation-quote badge bg-secondary" style="max-width: 50%; white-space: normal; text-align:left;"></span>
                <select class="form-select form-select-sm annotation-kind" style="width: auto;" aria-label="标注类型">
                    <option value="note">批注</option>
                    <option value="grammar">语法</option>
                    <option value="terminology">术语</option>
                    <option value="style">风格</option>
                </select>
                <input class="form-control form-control-sm annotation-note" style="flex:1; min-width: 160px;" placeholder="标注内容">
                <button class="btn btn-sm btn-primary" onclick="saveAnnotation(this)">保存</button>
                <button class="btn btn-sm btn-light" onclick="cancelAnnotation(this)">取消</button>
            </div>
        </div>
        <div class="performance-metrics mt-1" style="display: none;">
            <small class="text-muted d-flex justify-content-between">
                <span class="tokens-per-second"></span>
                <span class="translation-time"></span>
            </small>
        </div>
        <div class="team-review-cards mt-1"></div>
        <div class="evaluation-result mt-1"></div>
        <div class="grade-result mt-1"></div>
        <div class="polish-result mt-1"></div>
        <div class="annotations mt-1"></div>
    `;
    
    if (window.TC_I18N) TC_I18N.apply(newItem);
    container.appendChild(newItem);
}

// 检查语言重复
function checkLanguageDuplication(changedSelect) {
    const allSelects = document.querySelectorAll('#translateWorkspace .target-lang-select');
    const selectedValues = [];
    
    allSelects.forEach(select => {
        selectedValues.push(select.value);
    });
    
    // 检查是否有重复
    const hasDuplicates = selectedValues.length !== new Set(selectedValues).size;
    
    if (hasDuplicates) {
        // 找到第一个未使用的语言
        const availableLangs = ['zh-cn', 'zh-tw', 'en', 'ja', 'ko', 'es', 'fr', 'de', 'it', 'ru', 'ar', 'pt'];
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
    if (document.querySelectorAll('#translateWorkspace .target-lang-item').length > 1) {
        item.remove();
    } else {
        alert(t('keepOneLang'));
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
        
        displayEvaluation(evaluationDiv, response.data.data || {});
        
    } catch (error) {
        evaluationDiv.innerHTML = `<span class="tc-error">评估失败: ${error.message}</span>`;
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
        btn.innerHTML = t('copied');
        setTimeout(() => {
            btn.innerHTML = t('copy');
        }, 2000);
    });
}

// 显示术语库模态框
function showTerminologyModal() {
    const modal = new bootstrap.Modal(document.getElementById('terminologyModal'));
    modal.show();
}

// 显示向量数据库模态框
// ---- 翻译记忆库（外置记忆）入口：概况徽标 + 检索 ----
async function loadTMStats() {
    try {
        const response = await axios.get('/api/vector-db/stats');
        const d = response.data.data || response.data;
        const total = d.total_items || 0;
        const badge = document.getElementById('tmBadge');
        if (badge) badge.textContent = total;
        const stats = document.getElementById('tmStats');
        if (stats) {
            const langs = Object.entries(d.language_counts || {})
                .map(([l, c]) => `${l}: ${c}`).join(' · ');
            stats.textContent = `${total} 条` + (langs ? `（${langs}）` : '');
        }
    } catch (e) {
        console.error('TM stats failed:', e);
    }
}

async function searchTM() {
    const query = (document.getElementById('tmQuery') || {}).value || '';
    const box = document.getElementById('tmResults');
    if (!query.trim() || !box) return;
    box.innerHTML = '<span class="text-muted">检索中…</span>';
    try {
        const response = await axios.post('/api/vector-db/search', { query: query, k: 6 });
        const results = (response.data.data || {}).results || {};
        let html = '';
        Object.entries(results).forEach(([lang, items]) => {
            html += `<div class="fw-bold mt-1">${lang}</div>`;
            items.forEach(it => {
                html += `<div class="border rounded px-2 py-1 mb-1">` +
                    `<div class="text-truncate">${it.source}</div>` +
                    `<div class="text-truncate text-secondary">${it.translation}</div>` +
                    `<span class="badge bg-secondary">${(it.similarity * 100).toFixed(0)}%</span></div>`;
            });
        });
        box.innerHTML = html || '<span class="text-muted">无相似记忆</span>';
        track('memory.search', { has_hits: !!html });
    } catch (e) {
        box.innerHTML = '<span class="tc-error">检索失败</span>';
    }
}

function showVectorDBModal() {
    const modal = new bootstrap.Modal(document.getElementById('vectorDBModal'));
    modal.show();
    loadTMStats();
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
        translateBtn.innerHTML = t('stop');
        translateBtn.onclick = stopTranslation;
    } else {
        translateBtn.className = 'btn btn-success btn-sm me-2';
        translateBtn.innerHTML = t('translate');
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
        alert(t('enterSource'));
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
    textarea.style.backgroundColor = '';
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
                errorMsg += t('endpointDown');
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
        model: selectedModel,
        endpoint: currentEndpoint()
    });
    
    // 显示翻译结果
    const targetLang = targetLangs[0];
    const translation = response.data.data.translations[targetLang];
    if (response.data.data && response.data.data.memory) loadTMStats();
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
            model: selectedModel,
            endpoint: currentEndpoint()
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
            state.textarea.value = `${t('translationFailed')}: ${data.error}`;
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
    const firstTargetItem = document.querySelector('#translateWorkspace .target-lang-item');
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
    const otherTargetItems = document.querySelectorAll('#translateWorkspace .target-lang-item:not(:first-child)');
    otherTargetItems.forEach(item => {
        const textarea = item.querySelector('.translation-result');
        if (textarea) {
            textarea.value = '';
            textarea.style.backgroundColor = '';
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
    firstTargetTextarea.style.backgroundColor = '';
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
    saveWorkspaceState();
    track('workspace.swap', {});
}

// 获取语言显示名称
function getLanguageDisplayName(langCode) {
    const languageNames = {
        'auto': '自动检测',
        'zh-cn': '简体中文',
        'zh-tw': '繁体中文',
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
    
    swapBtn.innerHTML = '已互换';
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
    document.querySelectorAll('#translateWorkspace .target-lang-item').forEach((item, index) => {
        const _sel = item.querySelector('.target-lang-select');
        if (!_sel) return;
        const lang = _sel.value;
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
            translationStates[lang].statusDiv.innerHTML = t('preparing');
        }
    });
    
    // 对每个目标语言进行反思翻译
    for (const targetLang of targetLangs) {
        const state = translationStates[targetLang];
        
        try {
            // 第一步：初始翻译
            state.statusDiv.innerHTML = t('initialTranslating');
            await typewriterStatusEffect(state.textarea, t('initialTranslating'));
            
            const initialTranslation = await performSingleTranslation(
                sourceText, sourceLang, targetLang, useVectorDB, useTerminology, selectedModel
            );
            
            state.currentTranslation = initialTranslation;
            await typewriterEffect(state.textarea, initialTranslation, true, 20);
            state.statusDiv.innerHTML = t('initialDone');
            
            // 进行反思和优化轮次
            for (let round = 1; round <= reflectionRounds; round++) {
                state.statusDiv.innerHTML = t('reflecting').replace('{n}', round);
                await typewriterStatusEffect(state.textarea, `第${round}轮反思分析中...`);
                
                // 反思阶段
                const reflectionResult = await performReflection(
                    sourceText, state.currentTranslation, sourceLang, targetLang, selectedModel
                );
                state.reflections.push(reflectionResult.reflection);
                
                state.statusDiv.innerHTML = t('improving').replace('{n}', round);
                await typewriterStatusEffect(state.textarea, `第${round}轮优化改进中...`);
                
                // 优化阶段
                const improvementResult = await performImprovement(
                    sourceText, state.currentTranslation, reflectionResult.reflection, sourceLang, targetLang, selectedModel
                );
                
                state.currentTranslation = improvementResult.improved_translation;
                state.improvements.push(improvementResult.improved_translation);
                await typewriterEffect(state.textarea, improvementResult.improved_translation, true, 15);
                
                state.statusDiv.innerHTML = t('improvedDone').replace('{n}', round);
                
                // 短暂延迟以显示进度
                await new Promise(resolve => setTimeout(resolve, 800));
            }
            
            // 最终状态
            state.textarea.className = 'form-control translation-result translation-completed';
            state.statusDiv.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <span>${t('reflectionDone').replace('{n}', reflectionRounds)}</span>
                    <button class="btn btn-sm btn-outline-info" onclick="showReflectionDetails('${targetLang}')">
                        查看详情
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
            state.statusDiv.innerHTML = t('translationFailed');
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
        model: selectedModel,
        endpoint: currentEndpoint()
    });
    
    return response.data.data.translations[targetLang].text;
}

// 执行反思
async function performReflection(sourceText, translation, sourceLang, targetLang, selectedModel) {
    const response = await axios.post('/api/translate/reflect', {
        source_text: sourceText,
        translation: translation,
        source_lang: sourceLang,
        target_lang: targetLang,
        model: selectedModel,
        endpoint: currentEndpoint()
    });
    
    return {
        reflection: (response.data.data || {}).reflection,
        metrics: (response.data.data || {}).metrics
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
        model: selectedModel,
        endpoint: currentEndpoint()
    });
    
    return {
        improved_translation: (response.data.data || {}).improved_translation,
        metrics: (response.data.data || {}).metrics
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
                        <h6>反思意见：</h6>
                        <div class="bg-light p-2 rounded mb-3">${escapeHtml(reflection)}</div>
                        <h6>优化结果：</h6>
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
        statusDiv.innerHTML = t('preparing');
        
        // 第一步：初始翻译
        statusDiv.innerHTML = t('initialTranslating');
        await typewriterStatusEffect(textarea, t('initialTranslating'));
        
        const initialTranslation = await performSingleTranslation(
            sourceText, sourceLang, targetLang, useVectorDB, useTerminology, selectedModel
        );
        
        translationState.currentTranslation = initialTranslation;
        await typewriterEffect(textarea, initialTranslation, true, 20);
        statusDiv.innerHTML = t('initialDone');
        
        // 进行反思和优化轮次
        for (let round = 1; round <= reflectionRounds; round++) {
            statusDiv.innerHTML = t('reflecting').replace('{n}', round);
            await typewriterStatusEffect(textarea, `第${round}轮反思分析中...`);
            
            // 反思阶段
            const reflectionResult = await performReflection(
                sourceText, translationState.currentTranslation, sourceLang, targetLang, selectedModel
            );
            translationState.reflections.push(reflectionResult.reflection);
            
            statusDiv.innerHTML = t('improving').replace('{n}', round);
            await typewriterStatusEffect(textarea, `第${round}轮优化改进中...`);
            
            // 优化阶段
            const improvementResult = await performImprovement(
                sourceText, translationState.currentTranslation, reflectionResult.reflection, sourceLang, targetLang, selectedModel
            );
            
            translationState.currentTranslation = improvementResult.improved_translation;
            translationState.improvements.push(improvementResult.improved_translation);
            await typewriterEffect(textarea, improvementResult.improved_translation, true, 15);
            
            statusDiv.innerHTML = t('improvedDone').replace('{n}', round);
            
            // 短暂延迟以显示进度
            await new Promise(resolve => setTimeout(resolve, 800));
        }
        
        // 最终状态
        textarea.className = 'form-control translation-result translation-completed';
        statusDiv.innerHTML = `
            <div class="d-flex justify-content-between align-items-center">
                <span>${t('reflectionDone').replace('{n}', reflectionRounds)}</span>
                <button class="btn btn-sm btn-outline-info" onclick="showSingleReflectionDetails('${targetLang}', ${JSON.stringify(translationState).replace(/"/g, '&quot;')})">
                    查看详情
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
        statusDiv.innerHTML = '翻译失败';
    }
}

// 显示单独反思详情（简化版本，直接使用传入的数据）
function showSingleReflectionDetails(targetLang, translationState) {
    const translation = currentTranslations?.translations[targetLang];
    if (!translation || !translation.reflections) {
        alert('没有找到反思详情');
        return;
    }
    
    showReflectionDetails(targetLang);
}

function renderEndpointManager(endpoints) {
    const box = document.getElementById('endpointManager');
    if (!box) return;
    box.innerHTML = (endpoints || []).map(function (ep) {
        const models = (ep.models || []).join(', ');
        const badge = ep.editable
            ? '<span class="badge bg-dark">user</span>'
            : '<span class="badge bg-secondary">' + _esc(ep.source || '') + '</span>';
        const act = ep.editable
            ? '<button class="btn btn-sm btn-link tc-error p-0" onclick="deleteManualEndpoint(\'' + _esc(ep.name) + '\')">' + t('remove') + '</button>'
            : '<button class="btn btn-sm btn-link p-0" onclick="importEndpoint(\'' + _esc(ep.name) + '\')">' + t('importBtn') + '</button>';
        return '<div class="d-flex justify-content-between align-items-start gap-2 border-bottom py-1">' +
            '<div><div><strong>' + _esc(ep.name) + '</strong> ' + badge +
            (ep.masked_key ? ' <span class="muted">' + _esc(ep.masked_key) + '</span>' : '') +
            '</div><div class="muted">' + _esc(ep.base_url || '') +
            (models ? ' · ' + _esc(models) : '') + '</div></div>' +
            '<div class="text-nowrap">' + act + '</div></div>';
    }).join('');
}

async function importEndpoint(name) {
    try {
        await axios.post('/api/endpoints/import', { name: name });
        track('endpoint.import', { name: name });
        await loadEndpoints();
    } catch (e) {
        alert((e.response && e.response.data && e.response.data.error) || e.message);
    }
}

async function deleteManualEndpoint(name) {
    try {
        await axios.delete('/api/endpoints/manual/' + encodeURIComponent(name));
        track('endpoint.delete', { name: name });
        await loadEndpoints();
    } catch (e) {
        alert((e.response && e.response.data && e.response.data.error) || e.message);
    }
}

async function saveManualEndpoint() {
    const name = (document.getElementById('epName') || {}).value || '';
    const baseUrl = (document.getElementById('epBaseUrl') || {}).value || '';
    const apiKey = (document.getElementById('epKey') || {}).value || '';
    const models = (document.getElementById('epModels') || {}).value || '';
    if (!name.trim() || !baseUrl.trim()) return;
    try {
        await axios.post('/api/endpoints/manual', {
            name: name.trim(),
            base_url: baseUrl.trim(),
            api_key: apiKey.trim() || undefined,
            models: models,
        });
        track('endpoint.manual_save', { name: name.trim() });
        ['epName', 'epBaseUrl', 'epKey', 'epModels'].forEach(function (id) {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
        await loadEndpoints();
    } catch (e) {
        alert((e.response && e.response.data && e.response.data.error) || e.message);
    }
}

async function showSettingsModal() {
    const modal = new bootstrap.Modal(document.getElementById('settingsModal'));

    loadAvailableModels();
    loadReviewerModels();
    try {
        const response = await axios.get('/api/config');
        document.getElementById('useProxy').checked = response.data.use_proxy || false;
        document.getElementById('proxyUrl').value = response.data.proxy_url || '';
    } catch (error) {
        console.error('Failed to load config:', error);
    }

    modal.show();
}

async function saveSettings() {
    const useProxy = document.getElementById('useProxy').checked;
    const proxyUrl = document.getElementById('proxyUrl').value;
    
    try {
        const response = await axios.post('/api/config', {
            use_proxy: useProxy,
            proxy_url: proxyUrl
        });
        
        alert(response.data.message);
        
        const modal = bootstrap.Modal.getInstance(document.getElementById('settingsModal'));
        modal.hide();
        
    } catch (error) {
        alert('保存设置失败: ' + (error.response?.data?.error || error.message));
    }
} 

// =========================================================================
// Teaching: telemetry + per-language grading, polishing, annotations
// =========================================================================

function track(event, payload) {
    try {
        axios.post('/api/telemetry', { event: event, payload: payload || {} }, { timeout: 4000 }).catch(function () {});
    } catch (e) { /* telemetry must never break the UI */ }
}

function _langItem(el) { return el.closest('.target-lang-item'); }
function _langCode(item) { return item.querySelector('.target-lang-select').value; }
function _langText(item) { return item.querySelector('.translation-result'); }

function renderGradeInto(item, g) {
    const box = item.querySelector('.grade-result');
    if (!box) return;
    if (g.error) {
        box.innerHTML = '<span class="tc-error">评分出错：' + g.error + '</span>';
        return;
    }
    const scores = g.scores || {};
    let html = '<div class="d-flex gap-2 flex-wrap mb-2">';
    html += '<div class="score-chip overall"><span class="value">' +
        (g.overall === null || g.overall === undefined ? '—' : g.overall) +
        '</span><span class="label">' + t('total') + '</span></div>';
    const dimNames = { adequacy: 'adequacy', fluency: 'fluency', terminology: 'terminology', culture: 'culture' };
    Object.entries(scores).forEach(function (kv) {
        html += '<div class="score-chip"><span class="value">' + kv[1] +
            '</span><span class="label">' + t(dimNames[kv[0]] || kv[0]) + '</span></div>';
    });
    html += '</div>';
    html += (g.issues || []).map(function (i) {
        return '<div class="issue-row"><span class="tag ' + i.type + '">' + i.type +
            '</span><div><div>' + (i.span || '') + '</div><div class="muted">' + (i.advice || '') + '</div></div></div>';
    }).join('');
    box.innerHTML = html;
}

async function gradeLanguage(btn) {
    const item = _langItem(btn);
    const source = document.getElementById('sourceText').value.trim();
    const text = _langText(item).value.trim();
    const box = item.querySelector('.grade-result');
    if (!source || !text) {
        box.innerHTML = '<span class="tc-error">' + t('missingText') + '</span>';
        return;
    }
    box.innerHTML = '<span class="muted">' + t('grading') + '</span>';
    try {
        const resp = await axios.post('/api/human/grade', {
            source_text: source,
            translation: text,
            source_lang: document.getElementById('sourceLang').value,
            target_lang: _langCode(item),
            endpoint: currentReviewerEndpoint(),
            model: currentReviewerModel() || undefined,
            author: (document.getElementById('authorInput') || {}).value || undefined,
        }, { timeout: 240000 });
        const g = resp.data.grade || {};
        if (resp.data.submission_id) {
            item.dataset.submissionId = resp.data.submission_id;
            item.querySelector('.submission-hint').textContent = t('saved') + ' #' + resp.data.submission_id;
        }
        renderGradeInto(item, g);
        loadAnnotationsInto(item);
        track('human.grade', { overall: g.overall, issues: (g.issues || []).length, target_lang: _langCode(item) });
    } catch (e) {
        const timedOut = e.code === 'ECONNABORTED' || /timeout/i.test(e.message || '');
        box.innerHTML = '<span class="tc-error">' + (timedOut ? '评分超时：评审端点无响应，请在设置里换一个评审模型' :
            ('评分失败：' + ((e.response && e.response.data && e.response.data.error) || e.message))) + '</span>';
    }
}

function renderPolishInto(item, p) {
    const box = item.querySelector('.polish-result');
    if (!box) return;
    if (!p.parse_ok) {
        box.innerHTML = '<span class="tc-error">润色结果解析失败</span>' +
            (p.polished ? '<div class="mt-1">' + p.polished + '</div>' : '');
        return;
    }
    const edits = (p.edits || []).map(function (e) {
        return '<div class="edit-row"><span class="tag">' + e.type + '</span><div>' +
            '<div><s class="muted">' + (e.original || '') + '</s> → ' + (e.revised || '') + '</div>' +
            '<div class="muted">' + (e.reason || '') + '</div></div></div>';
    }).join('');
    box.innerHTML =
        '<div class="card"><div class="card-header py-2">' + t('polish') + '</div>' +
        '<div class="card-body py-2"><div class="polished-text" style="white-space:pre-wrap;line-height:1.6;">' +
        (p.polished || '') + '</div>' +
        (p.summary ? '<div class="muted mt-1">' + p.summary + '</div>' : '') +
        '<button class="btn btn-sm btn-light mt-2" onclick="applyPolish(this)">应用到译文</button>' +
        '</div></div>' + (edits ? '<div class="mt-2">' + edits + '</div>' : '');
}

async function polishLanguage(btn) {
    const item = _langItem(btn);
    const source = document.getElementById('sourceText').value.trim();
    const text = _langText(item).value.trim();
    const box = item.querySelector('.polish-result');
    if (!source || !text) {
        box.innerHTML = '<span class="tc-error">' + t('missingText') + '</span>';
        return;
    }
    box.innerHTML = '<span class="muted">' + t('polishing') + '</span>';
    try {
        const resp = await axios.post('/api/human/polish', {
            source_text: source,
            translation: text,
            source_lang: document.getElementById('sourceLang').value,
            target_lang: _langCode(item),
            endpoint: currentReviewerEndpoint(),
            model: currentReviewerModel() || undefined,
        }, { timeout: 240000 });
        const p = resp.data.polish || {};
        renderPolishInto(item, p);
        track('human.polish', { edits: (p.edits || []).length, parse_ok: p.parse_ok, target_lang: _langCode(item) });
    } catch (e) {
        const timedOut = e.code === 'ECONNABORTED' || /timeout/i.test(e.message || '');
        box.innerHTML = '<span class="tc-error">' + (timedOut ? '润色超时：评审端点无响应，请在设置里换一个评审模型' :
            ('润色失败：' + ((e.response && e.response.data && e.response.data.error) || e.message))) + '</span>';
    }
}

function applyPolish(btn) {
    const item = _langItem(btn);
    const polished = item.querySelector('.polished-text');
    if (!polished) return;
    _langText(item).value = polished.textContent;
    delete item.dataset.submissionId;
    item.querySelector('.submission-hint').textContent = '';
}

function beginAnnotation(btn) {
    const item = _langItem(btn);
    const ta = _langText(item);
    const sel = ta.value.substring(ta.selectionStart, ta.selectionEnd);
    const form = item.querySelector('.annotation-form');
    if (!sel.trim()) {
        form.style.display = 'none';
        return;
    }
    item.dataset.annStart = ta.selectionStart;
    item.dataset.annEnd = ta.selectionEnd;
    item.dataset.annQuote = sel;
    const q = item.querySelector('.annotation-quote');
    q.textContent = sel.length > 80 ? sel.slice(0, 80) + '…' : sel;
    form.style.display = 'block';
    item.querySelector('.annotation-note').focus();
}

function cancelAnnotation(btn) {
    const item = _langItem(btn);
    item.querySelector('.annotation-form').style.display = 'none';
    item.querySelector('.annotation-note').value = '';
}

async function ensureSubmissionFor(item) {
    if (item.dataset.submissionId) return item.dataset.submissionId;
    const resp = await axios.post('/api/human/submissions', {
        source_text: document.getElementById('sourceText').value,
        translation: _langText(item).value,
        source_lang: document.getElementById('sourceLang').value,
        target_lang: _langCode(item),
        endpoint: currentReviewerEndpoint(),
        model: currentReviewerModel() || undefined,
        author: (document.getElementById('authorInput') || {}).value || undefined,
    });
    const id = (resp.data.submission || {}).id || null;
    if (id) {
        item.dataset.submissionId = id;
        item.querySelector('.submission-hint').textContent = t('saved') + ' #' + id;
    }
    return id;
}

async function saveAnnotation(btn) {
    const item = _langItem(btn);
    const note = item.querySelector('.annotation-note').value.trim();
    if (!note || !item.dataset.annQuote) return;
    try {
        const sid = await ensureSubmissionFor(item);
        await axios.post('/api/human/annotations', {
            submission_id: sid,
            quote: item.dataset.annQuote,
            note: note,
            kind: item.querySelector('.annotation-kind').value,
            start: parseInt(item.dataset.annStart),
            end: parseInt(item.dataset.annEnd),
            target_lang: _langCode(item),
            author: (document.getElementById('authorInput') || {}).value || undefined,
        });
        track('annotation.add', { kind: item.querySelector('.annotation-kind').value, target_lang: _langCode(item) });
        cancelAnnotation(btn);
        loadAnnotationsInto(item);
    } catch (e) {
        alert('标注保存失败: ' + ((e.response && e.response.data && e.response.data.error) || e.message));
    }
}

const ALIGN_PALETTE = ['#c9d9e4', '#e6e8ea', '#a9c0d0', '#f0f1f2', '#8fa9bb', '#d5dbe0', '#bfcbd4', '#e9edf0'];

function _esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
}

function _alignSpans(text, rows, side) {
    const spans = [];
    rows.forEach(function (a, i) {
        const quote = side === 'src' ? a.src_quote : a.quote;
        if (!quote) return;
        let start = side === 'src' ? a.src_start : a.start;
        let end = side === 'src' ? a.src_end : a.end;
        const valid = Number.isInteger(start) && Number.isInteger(end) && end > start &&
            text.slice(start, end) === quote;
        if (!valid) {
            const idx = text.indexOf(quote);
            if (idx < 0) return;
            start = idx;
            end = idx + quote.length;
        }
        spans.push({ start: start, end: end, color: ALIGN_PALETTE[i % ALIGN_PALETTE.length], label: i + 1 });
    });
    return spans.sort(function (a, b) { return a.start - b.start; });
}

function _highlight(text, spans) {
    if (!spans.length) return '';
    let html = '', pos = 0;
    spans.forEach(function (s) {
        if (s.start < pos) return;
        html += _esc(text.slice(pos, s.start));
        html += '<mark style="background:' + s.color + '" title="' + s.label + '">' +
            _esc(text.slice(s.start, s.end)) + '</mark>';
        pos = s.end;
    });
    return html + _esc(text.slice(pos));
}

function renderAlignPreviews(item, rows) {
    const srcBox = item.querySelector('.align-preview-src');
    const tgtBox = item.querySelector('.align-preview-tgt');
    if (!srcBox || !tgtBox) return;
    const aligns = (rows || []).filter(function (a) { return a.kind === 'alignment'; });
    const srcText = document.getElementById('sourceText').value;
    const tgtText = _langText(item).value;
    const srcSpans = _alignSpans(srcText, aligns, 'src');
    const tgtSpans = _alignSpans(tgtText, aligns, 'tgt');
    if (!srcSpans.length && !tgtSpans.length) {
        srcBox.className = 'align-preview-src align-preview';
        tgtBox.className = 'align-preview-tgt align-preview';
        srcBox.innerHTML = '';
        tgtBox.innerHTML = '';
        return;
    }
    srcBox.className = 'align-preview-src align-preview has-content';
    tgtBox.className = 'align-preview-tgt align-preview has-content';
    srcBox.innerHTML = _highlight(srcText, srcSpans);
    tgtBox.innerHTML = _highlight(tgtText, tgtSpans);
}

async function loadAnnotationsInto(item) {
    const box = item.querySelector('.annotations');
    if (!box || !item.dataset.submissionId) return;
    try {
        const resp = await axios.get('/api/human/annotations', {
            params: { submission_id: item.dataset.submissionId },
        });
        const rows = resp.data.annotations || [];
        box.innerHTML = rows.map(function (a) {
            const body = a.src_quote
                ? '<div>「' + a.src_quote + '」 ↔ 「' + (a.quote || '') + '」</div>'
                : '<div>「' + (a.quote || '') + '」</div>';
            return '<div class="annotation-row"><span class="tag">' + (a.kind || 'note') + '</span>' +
                '<div style="flex:1;">' + body +
                (a.note ? '<div class="muted">' + a.note + '</div>' : '') + '</div>' +
                '<button class="btn btn-sm btn-link tc-error" onclick="deleteAnnotationIn(this, \'' + a.id +
                '\')">×</button></div>';
        }).join('');
        renderAlignPreviews(item, rows);
    } catch (e) {
        box.innerHTML = '';
    }
}

async function deleteAnnotationIn(btn, id) {
    const item = _langItem(btn);
    try {
        await axios.delete('/api/human/annotations/' + id);
        loadAnnotationsInto(item);
    } catch (e) { /* ignore */ }
}

async function quickScore(btn) {
    const item = _langItem(btn);
    const source = document.getElementById('sourceText').value.trim();
    const text = _langText(item).value.trim();
    const box = item.querySelector('.quick-result');
    if (!source || !text) {
        box.innerHTML = '<span class="tc-error">' + t('missingText') + '</span>';
        return;
    }
    box.innerHTML = '<span class="muted">' + t('computing') + '</span>';
    try {
        const payload = {
            source_text: source,
            translation: text,
            source_lang: document.getElementById('sourceLang').value,
            target_lang: _langCode(item),
        };
        if (item.dataset.reference && item.dataset.reference.trim() && item.dataset.reference !== text) {
            payload.reference = item.dataset.reference;
        }
        const resp = await axios.post('/api/human/quick-score', payload, { timeout: 60000 });
        const s = resp.data.score || {};
        let html = '<div class="d-flex gap-2 flex-wrap">';
        html += '<div class="score-chip overall"><span class="value">' + (s.semantic_score ?? '—') +
            '</span><span class="label">' + t('semantic') + '</span></div>';
        html += '<div class="score-chip"><span class="value">' +
            (s.semantic_similarity !== undefined ? Math.round(s.semantic_similarity * 100) + '%' : '—') +
            '</span><span class="label">' + t('semanticSim') + '</span></div>';
        if (s.combined_score !== undefined) {
            html += '<div class="score-chip"><span class="value">' + s.combined_score +
                '</span><span class="label">' + t('combined') + '</span></div>';
        }
        if (s.chrf !== undefined && s.chrf !== null) {
            html += '<div class="score-chip"><span class="value">' + s.chrf +
                '</span><span class="label">chrF</span></div>';
        }
        html += '</div><div class="muted small mt-1">' + (s.latency_ms || 0) + ' ms</div>';
        box.innerHTML = html;
        track('human.quick_score', {
            semantic_score: s.semantic_score, combined_score: s.combined_score, target_lang: _langCode(item)
        });
    } catch (e) {
        box.innerHTML = '<span class="tc-error">' + t('quickFail') + '</span>';
    }
}

async function autoAlign(btn) {
    const item = _langItem(btn);
    const source = document.getElementById('sourceText').value.trim();
    const text = _langText(item).value.trim();
    const pairsBox = item.querySelector('.align-pairs');
    if (!source || !text) {
        pairsBox.innerHTML = '<span class="tc-error">' + t('missingText') + '</span>';
        return;
    }
    pairsBox.innerHTML = '<span class="muted">' + t('computing') + '</span>';
    try {
        const resp = await axios.post('/api/human/align', {
            source_text: source,
            translation: text,
            source_lang: document.getElementById('sourceLang').value,
            target_lang: _langCode(item),
        }, { timeout: 60000 });
        const a = resp.data.alignment || {};
        renderAutoAlignment(item, a.pairs || []);
        track('human.auto_align', { pairs: (a.pairs || []).length, target_lang: _langCode(item) });
    } catch (e) {
        pairsBox.innerHTML = '<span class="tc-error">' + ((e.response && e.response.data && e.response.data.error) || e.message) + '</span>';
    }
}

function renderAutoAlignment(item, pairs) {
    const srcBox = item.querySelector('.align-preview-src');
    const tgtBox = item.querySelector('.align-preview-tgt');
    const listBox = item.querySelector('.align-pairs');
    if (!srcBox || !tgtBox || !listBox) return;
    const srcText = document.getElementById('sourceText').value;
    const tgtText = _langText(item).value;
    const color = function (i) { return ALIGN_PALETTE[i % ALIGN_PALETTE.length]; };
    const srcSpans = pairs.map(function (p, i) {
        return { start: p.src_start, end: p.src_end, color: color(i), label: i + 1 };
    });
    const tgtSpans = pairs.map(function (p, i) {
        return { start: p.tgt_start, end: p.tgt_end, color: color(i), label: i + 1 };
    });
    srcBox.className = 'align-preview-src align-preview has-content';
    tgtBox.className = 'align-preview-tgt align-preview has-content';
    srcBox.innerHTML = _highlight(srcText, srcSpans);
    tgtBox.innerHTML = _highlight(tgtText, tgtSpans);
    listBox.innerHTML = pairs.map(function (p, i) {
        return '<div class="align-pair-row">' +
            '<span class="align-swatch" style="background:' + color(i) + '"></span>' +
            '<span>' + _esc(p.src) + '</span><span class="muted">↔</span>' +
            '<span>' + _esc(p.tgt) + '</span>' +
            '<span class="muted small">' + Math.round(p.score * 100) + '%</span></div>';
    }).join('');
}

async function showAnalyticsModal() {
    const modal = new bootstrap.Modal(document.getElementById('analyticsModal'));
    modal.show();
    const body = document.getElementById('analyticsBody');
    body.innerHTML = '加载中…';
    try {
        const resp = await axios.get('/api/telemetry/summary', { params: { days: 7 } });
        const s = resp.data.summary || {};
        const events = Object.entries(s.events_by_type || {})
            .map(function (kv) { return '<span class="badge bg-light text-dark border me-1">' + kv[0] + ': ' + kv[1] + '</span>'; })
            .join('');
        const days = Object.entries(s.events_by_day || {})
            .map(function (kv) { return kv[0] + ': ' + kv[1]; }).join(' · ');
        body.innerHTML =
            '<div class="row g-2 mb-3">' +
            '<div class="col-6 col-md-3"><div class="score-chip"><span class="value">' + (s.events_total || 0) + '</span><span class="label">事件</span></div></div>' +
            '<div class="col-6 col-md-3"><div class="score-chip"><span class="value">' + (s.submissions || 0) + '</span><span class="label">提交</span></div></div>' +
            '<div class="col-6 col-md-3"><div class="score-chip"><span class="value">' + (s.avg_overall_score === null ? '—' : s.avg_overall_score) + '</span><span class="label">平均分</span></div></div>' +
            '<div class="col-6 col-md-3"><div class="score-chip"><span class="value">' + (s.annotations || 0) + '</span><span class="label">标注</span></div></div>' +
            '</div>' +
            '<div class="mb-2">' + (events || '<span class="muted">无事件</span>') + '</div>' +
            '<div class="muted">' + (days || '') + '</div>';
    } catch (e) {
        body.innerHTML = '<span class="tc-error">学情加载失败</span>';
    }
}

// =========================================================================
// Read-aloud (TTS + recording + pronunciation scoring)
// =========================================================================
let _speechPassage = null;
let _mediaRecorder = null;
let _recChunks = [];
let _recStream = null;
let _recTimer = null;
let _recStart = 0;

async function loadSpeechPassage() {
    try {
        const resp = await axios.get('/api/speech/passage');
        _speechPassage = resp.data.passage || {};
        const level = document.getElementById('speechLevel');
        const text = document.getElementById('speechText');
        if (level) level.textContent = _speechPassage.level || '';
        if (text) text.textContent = _speechPassage.text || '';
        const audio = document.getElementById('speechAudio');
        if (audio) { audio.pause(); audio.removeAttribute('src'); audio.style.display = 'none'; }
        const box = document.getElementById('speechResult');
        if (box) box.innerHTML = '';
        const hint = document.getElementById('speechTTSHint');
        if (hint) hint.textContent = '';
        saveWorkspaceState();
    } catch (e) {
        const text = document.getElementById('speechText');
        if (text) text.innerHTML = '<span class="tc-error">' + (e.message || '') + '</span>';
    }
}

async function speechTTS() {
    const text = (_speechPassage || {}).text || document.getElementById('speechText').textContent || '';
    const hint = document.getElementById('speechTTSHint');
    const audio = document.getElementById('speechAudio');
    if (!text.trim()) return;
    if (hint) hint.textContent = t('computing');
    try {
        const resp = await axios.post('/api/speech/tts', { text: text, lang: 'zh' }, { timeout: 120000 });
        if (audio) {
            audio.src = resp.data.url;
            audio.style.display = '';
            audio.play().catch(function () {});
        }
        if (hint) hint.textContent = (resp.data.audio || {}).voice || '';
        track('speech.tts', { chars: text.length });
    } catch (e) {
        if (hint) hint.textContent = (e.response && e.response.data && e.response.data.error) || e.message;
    }
}

function toggleRecording() {
    if (_mediaRecorder && _mediaRecorder.state === 'recording') {
        stopRecording();
    } else {
        startRecording();
    }
}

async function startRecording() {
    const btn = document.getElementById('recordBtn');
    try {
        _recStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        _recChunks = [];
        _mediaRecorder = new MediaRecorder(_recStream);
        _mediaRecorder.ondataavailable = function (e) { if (e.data && e.data.size) _recChunks.push(e.data); };
        _mediaRecorder.onstop = onRecordingStop;
        _mediaRecorder.start();
        _recStart = Date.now();
        if (btn) { btn.textContent = t('stop'); btn.className = 'btn btn-sm btn-outline-danger'; }
        const status = document.getElementById('speechStatus');
        if (status) status.textContent = '';
        _recTimer = setInterval(function () {
            const el = document.getElementById('recordTimer');
            if (el) el.textContent = ((Date.now() - _recStart) / 1000).toFixed(1) + 's';
        }, 100);
    } catch (e) {
        alert((e && e.message) || 'microphone unavailable');
    }
}

function stopRecording() {
    if (_mediaRecorder && _mediaRecorder.state === 'recording') _mediaRecorder.stop();
    if (_recStream) {
        _recStream.getTracks().forEach(function (tr) { tr.stop(); });
        _recStream = null;
    }
    if (_recTimer) { clearInterval(_recTimer); _recTimer = null; }
}

async function onRecordingStop() {
    const btn = document.getElementById('recordBtn');
    if (btn) { btn.textContent = t('record'); btn.className = 'btn btn-sm btn-primary'; }
    const blob = new Blob(_recChunks, { type: 'audio/webm' });
    const audio = document.getElementById('recordAudio');
    if (audio) { audio.src = URL.createObjectURL(blob); audio.style.display = ''; }
    const box = document.getElementById('speechResult');
    if (box) box.innerHTML = '<span class="muted">' + t('grading') + '</span>';
    const target = (_speechPassage || {}).text || document.getElementById('speechText').textContent || '';
    const fd = new FormData();
    fd.append('file', blob, 'rec.webm');
    fd.append('target_text', target);
    fd.append('language', 'zh');
    try {
        const resp = await axios.post('/api/speech/score', fd, { timeout: 300000 });
        renderSpeechScore(resp.data.result || {}, target);
    } catch (e) {
        if (box) box.innerHTML = '<span class="tc-error">' +
            ((e.response && e.response.data && e.response.data.error) || e.message) + '</span>';
    }
}

function renderSpeechScore(r, targetText) {
    const box = document.getElementById('speechResult');
    if (!box) return;
    if (r.error) {
        box.innerHTML = '<span class="tc-error">' + _esc(r.error) + '</span>';
        return;
    }
    let html = '<div class="d-flex gap-2 flex-wrap mb-2">';
    html += '<div class="score-chip overall"><span class="value">' + (r.score ?? '—') +
        '</span><span class="label">' + t('total') + '</span></div>';
    html += '<div class="score-chip"><span class="value">' + (r.accuracy ?? '—') + '%' +
        '</span><span class="label">' + t('accuracy') + '</span></div>';
    html += '<div class="score-chip"><span class="value">' + (r.completeness ?? '—') + '%' +
        '</span><span class="label">' + t('completeness') + '</span></div>';
    html += '</div>';

    const status = {};
    (r.chars || []).forEach(function (c) { status[c.index] = c.status; });
    const text = targetText || (_speechPassage || {}).text || '';
    let marked = '';
    for (let i = 0; i < text.length; i++) {
        const ch = _esc(text[i]);
        if (status[i] === 'wrong') marked += '<span class="sp-wrong">' + ch + '</span>';
        else if (status[i] === 'missing') marked += '<span class="sp-missing">' + ch + '</span>';
        else marked += ch;
    }
    html += '<div class="reading-target mt-1">' + marked + '</div>';
    html += '<div class="muted small mt-2">' + t('transcript') + ': ' +
        _esc(r.transcript || '') + '</div>';
    box.innerHTML = html;
    saveWorkspaceState();
}

// =========================================================================
// Reading comprehension (CET-4 / CET-6 / postgraduate)
// =========================================================================
let _readingArticle = null;
let _readingCatalog = [];

function _fillSelect(sel, values, labelAll) {
    if (!sel) return;
    const keep = sel.value;
    sel.innerHTML = '';
    if (labelAll !== null && labelAll !== undefined) {
        const o = document.createElement('option');
        o.value = '';
        o.textContent = labelAll;
        sel.appendChild(o);
    }
    values.forEach(function (v) {
        const o = document.createElement('option');
        o.value = v;
        o.textContent = v;
        sel.appendChild(o);
    });
    if (values.indexOf(keep) >= 0 || sel.options.length === 1) sel.value = keep;
}

async function loadReadingCatalog() {
    try {
        const resp = await axios.get('/api/reading/catalog');
        _readingCatalog = resp.data.items || [];
        const examSel = document.getElementById('readingExam');
        if (examSel) {
            const known = Array.from(examSel.options).map(function (o) { return o.value; });
            Array.from(new Set(_readingCatalog.map(function (i) { return i.exam; }))).forEach(function (e) {
                if (e && known.indexOf(e) < 0) {
                    const o = document.createElement('option');
                    o.value = e;
                    o.textContent = e;
                    examSel.appendChild(o);
                }
            });
        }
        onReadingExamChange();
    } catch (e) {
        console.error(e);
    }
}

function onReadingExamChange() {
    const exam = (document.getElementById('readingExam') || {}).value || '';
    const rows = _readingCatalog.filter(function (i) { return i.exam === exam; });
    const years = Array.from(new Set(rows.map(function (i) { return i.year || ''; }).filter(Boolean))).sort();
    _fillSelect(document.getElementById('readingYear'), years, t('year') + ': *');
    onReadingYearChange();
}

function onReadingYearChange() {
    const exam = (document.getElementById('readingExam') || {}).value || '';
    const year = (document.getElementById('readingYear') || {}).value || '';
    const rows = _readingCatalog.filter(function (i) {
        return i.exam === exam && (!year || i.year === year);
    });
    const papers = Array.from(new Set(rows.map(function (i) { return i.paper || ''; }).filter(Boolean))).sort();
    _fillSelect(document.getElementById('readingPaper'), papers, t('paper') + ': *');
    onReadingPaperChange();
}

function onReadingPaperChange() {
    const exam = (document.getElementById('readingExam') || {}).value || '';
    const year = (document.getElementById('readingYear') || {}).value || '';
    const paper = (document.getElementById('readingPaper') || {}).value || '';
    const rows = _readingCatalog.filter(function (i) {
        return i.exam === exam && (!year || i.year === year) && (!paper || i.paper === paper);
    });
    const sel = document.getElementById('readingPick');
    if (!sel) return;
    sel.innerHTML = '<option value="">' + t('newArticle') + '…</option>';
    rows.forEach(function (i) {
        const o = document.createElement('option');
        o.value = i.id;
        o.textContent = i.title + (i.source === 'user' ? ' *' : '');
        sel.appendChild(o);
    });
}

async function openReadingArticle(id) {
    if (!id) return;
    try {
        const resp = await axios.get('/api/reading/article', { params: { id: id } });
        _readingArticle = resp.data.article || {};
        renderReadingArticle();
    } catch (e) {
        const body = document.getElementById('readingPassage');
        if (body) body.innerHTML = '<span class="tc-error">' + (e.message || '') + '</span>';
    }
}

async function loadReadingArticle() {
    const exam = (document.getElementById('readingExam') || {}).value || '';
    const year = (document.getElementById('readingYear') || {}).value || '';
    const paper = (document.getElementById('readingPaper') || {}).value || '';
    const title = document.getElementById('readingTitle');
    const body = document.getElementById('readingPassage');
    const res = document.getElementById('readingResult');
    if (res) res.innerHTML = '';
    if (body) body.innerHTML = '<span class="muted">' + t('loading') + '</span>';
    try {
        const resp = await axios.get('/api/reading/random', {
            params: { exam: exam || undefined, year: year || undefined, paper: paper || undefined },
        });
        _readingArticle = resp.data.article || {};
        const pick = document.getElementById('readingPick');
        if (pick) pick.value = _readingArticle.id || '';
        renderReadingArticle();
    } catch (e) {
        if (body) body.innerHTML = '<span class="tc-error">' + (e.message || '') + '</span>';
    }
}

function renderReadingArticle() {
    const title = document.getElementById('readingTitle');
    const body = document.getElementById('readingPassage');
    const meta = _readingArticle.source === 'user' ? ' · ' + (_readingArticle.year || '') +
        ' · ' + (_readingArticle.paper || '') : ' · ' + (_readingArticle.year || '');
    if (title) title.textContent = (_readingArticle.title || '') + meta;
    if (body) body.textContent = _readingArticle.passage || '';
    renderReadingQuestions(_readingArticle);
    const del = document.getElementById('readingDeleteBtn');
    if (del) del.style.display = _readingArticle.source === 'user' ? '' : 'none';
}

function renderReadingQuestions(article) {
    const box = document.getElementById('readingQuestions');
    if (!box) return;
    const qs = article.questions || [];
    box.innerHTML = qs.map(function (q, qi) {
        const opts = (q.options || []).map(function (opt, oi) {
            return '<label class="d-flex gap-2 align-items-start reading-option">' +
                '<input type="radio" name="rq' + qi + '" value="' + oi + '">' +
                '<span>' + String.fromCharCode(65 + oi) + '. ' + _esc(opt) + '</span></label>';
        }).join('');
        return '<div class="mb-3"><div class="fw-semibold mb-1">' + (qi + 1) + '. ' + _esc(q.q) + '</div>' + opts + '</div>';
    }).join('');
    box.dataset.count = String(qs.length);
}

async function submitReading() {
    if (!_readingArticle) return;
    const count = parseInt(document.getElementById('readingQuestions').dataset.count || '0', 10);
    const answers = [];
    for (let i = 0; i < count; i++) {
        const picked = document.querySelector('input[name="rq' + i + '"]:checked');
        answers.push(picked ? parseInt(picked.value, 10) : -1);
    }
    if (answers.some(function (a) { return a < 0; })) {
        document.getElementById('readingResult').innerHTML = '<span class="tc-error">' + t('missingText') + '</span>';
        return;
    }
    try {
        const resp = await axios.post('/api/reading/check', { id: _readingArticle.id, answers: answers });
        renderReadingResult(resp.data.result || {});
        track('reading.submit', { exam: (_readingArticle || {}).exam, score: (resp.data.result || {}).score });
    } catch (e) {
        document.getElementById('readingResult').innerHTML =
            '<span class="tc-error">' + ((e.response && e.response.data && e.response.data.error) || e.message) + '</span>';
    }
}

function renderReadingResult(r) {
    const box = document.getElementById('readingResult');
    if (!box) return;
    if (r.no_key) {
        let html = '<div class="muted mb-2">' + t('noKey') + '</div>';
        (r.details || []).forEach(function (d) {
            html += '<div class="issue-row"><span class="tag">' + (d.index + 1) + '</span><div>' +
                _esc(d.explain || '') + '</div></div>';
        });
        box.innerHTML = html;
        return;
    }
    let html = '<div class="d-flex gap-2 flex-wrap mb-2">' +
        '<div class="score-chip overall"><span class="value">' + (r.score ?? '—') + '/' + (r.total ?? '—') +
        '</span><span class="label">' + t('yourScore') + '</span></div>' +
        '<div class="score-chip"><span class="value">' + (r.percent ?? '—') + '%' +
        '</span><span class="label">' + t('yourScore') + '</span></div></div>';
    (r.details || []).forEach(function (d) {
        const mark = d.correct ? '<span class="badge bg-dark">' + t('correct') + '</span>'
            : '<span class="badge bg-secondary">' + t('wrong') + '</span>';
        html += '<div class="issue-row"><span class="tag">' + (d.index + 1) + '</span><div>' + mark +
            ' <span class="muted">' + t('explanation') + ': </span>' + _esc(d.explain || '') + '</div></div>';
    });
    box.innerHTML = html;
}

function showReadingImport() {
    new bootstrap.Modal(document.getElementById('readingImportModal')).show();
}

async function saveReadingImport() {
    const exam = (document.getElementById('impExam') || {}).value || 'cet4';
    const payload = {
        exam: exam,
        year: (document.getElementById('impYear') || {}).value || '',
        paper: (document.getElementById('impPaper') || {}).value || '',
        title: (document.getElementById('impTitle') || {}).value || '',
        passage: (document.getElementById('impPassage') || {}).value || '',
        questions: [],
    };
    try {
        payload.questions = JSON.parse((document.getElementById('impQuestions') || {}).value || '[]');
    } catch (e) {
        alert('JSON: ' + e.message);
        return;
    }
    try {
        const resp = await axios.post('/api/reading/import', payload);
        const modalEl = document.getElementById('readingImportModal');
        const m = bootstrap.Modal.getInstance(modalEl);
        if (m) m.hide();
        await loadReadingCatalog();
        const pick = document.getElementById('readingPick');
        if (pick) pick.value = resp.data.article.id;
        openReadingArticle(resp.data.article.id);
        ['impYear', 'impPaper', 'impTitle', 'impPassage', 'impQuestions'].forEach(function (id) {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
    } catch (e) {
        alert((e.response && e.response.data && e.response.data.error) || e.message);
    }
}

async function deleteReadingArticle() {
    if (!_readingArticle || _readingArticle.source !== 'user') return;
    try {
        await axios.delete('/api/reading/import/' + encodeURIComponent(_readingArticle.id));
        await loadReadingCatalog();
        loadReadingArticle();
    } catch (e) {
        alert((e.response && e.response.data && e.response.data.error) || e.message);
    }
}

// ---- real papers from GitHub -------------------------------------------
async function loadGithubOptions() {
    const src = (document.getElementById('ghSource') || {}).value || 'kaoyan1';
    const sel = document.getElementById('ghYear');
    const st = document.getElementById('ghStatus');
    if (st) st.textContent = t('loading');
    try {
        const resp = await axios.get('/api/reading/github/options', { timeout: 120000 });
        const options = resp.data.options || {};
        const list = src.indexOf('kaoyan') === 0 ? (options.kaoyan || []) : (options[src] || []);
        if (sel) {
            sel.innerHTML = '<option value="all">' + t('all') + '</option>' +
                list.map(function (v) { return '<option value="' + v + '">' + v + '</option>'; }).join('');
            if (list.length) sel.value = list[list.length - 1];
        }
        if (st) st.textContent = list.length ? (list.length + ' ✓') : '';
    } catch (e) {
        if (st) st.textContent = (e.response && e.response.data && e.response.data.error) || e.message;
    }
}

async function fetchRealPapers() {
    const src = (document.getElementById('ghSource') || {}).value || 'kaoyan1';
    const year = (document.getElementById('ghYear') || {}).value || '';
    const st = document.getElementById('ghStatus');
    if (st) st.textContent = t('loading');
    try {
        const resp = await axios.post('/api/reading/fetch_github', { source: src, year: year }, { timeout: 900000 });
        if (st) st.textContent = (resp.data.imported || 0) + ' ✓';
        await loadReadingCatalog();
        const arts = resp.data.articles || [];
        if (arts.length) {
            const last = arts[arts.length - 1];
            const pick = document.getElementById('readingPick');
            if (pick) pick.value = last.id;
            openReadingArticle(last.id);
            const modalEl = document.getElementById('readingImportModal');
            const m = bootstrap.Modal.getInstance(modalEl);
            if (m) m.hide();
        }
        track('reading.fetch_github', { source: src, year: year, imported: (resp.data.imported || 0) });
    } catch (e) {
        if (st) st.textContent = (e.response && e.response.data && e.response.data.error) || e.message;
    }
}

// ---- content library import / export -----------------------------------
function setContentStatus(msg) {
    const el = document.getElementById('contentStatus');
    if (el) el.textContent = msg;
}

async function exportContent(kind) {
    try {
        const resp = await axios.get('/api/content/export/' + kind, { responseType: 'blob', timeout: 60000 });
        const url = URL.createObjectURL(resp.data);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'transcoder-' + kind + '.json';
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        setContentStatus(t('exportDone'));
        track('content.export', { kind: kind });
    } catch (e) {
        setContentStatus((e.response && e.response.data && e.response.data.error) || e.message);
    }
}

async function importContent(kind, input) {
    const file = input && input.files && input.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    try {
        const resp = await axios.post('/api/content/import/' + kind, fd, { timeout: 180000 });
        setContentStatus((resp.data.imported || 0) + ' ✓ / ' + (resp.data.skipped || 0));
        if (kind === 'reading') await loadReadingCatalog();
        if (kind === 'writing') loadWritingPrompt();
        if (kind === 'speech') loadSpeechPassage();
        track('content.import', { kind: kind, imported: resp.data.imported || 0 });
    } catch (e) {
        setContentStatus((e.response && e.response.data && e.response.data.error) || e.message);
    } finally {
        input.value = '';
    }
}

// =========================================================================
// Draggable split panes (translate + writing)
// =========================================================================
function startSplit(splitter, ev) {
    if (ev) ev.preventDefault();
    const ws = splitter.closest('.ws');
    if (!ws || ws.classList.contains('is-collapsed')) return;
    const left = ws.querySelector('.ws-left');
    if (!left) return;
    const rect = ws.getBoundingClientRect();
    let pct = parseFloat(left.style.flexBasis) || 50;

    function onMove(e) {
        const lo = rect.left + Math.max(140, rect.width * 0.15);
        const hi = rect.right - Math.max(220, rect.width * 0.2);
        const x = Math.min(Math.max(e.clientX, lo), hi);
        pct = ((x - rect.left) / rect.width) * 100;
        left.style.flex = '0 0 ' + pct.toFixed(2) + '%';
    }
    function onUp() {
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        document.body.style.cursor = '';
        try { localStorage.setItem('tc_split_' + ws.id, String(pct)); } catch (e) { /* ignore */ }
        saveWorkspaceState();
    }
    document.body.style.cursor = 'col-resize';
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
}

function toggleLeftPane(btn) {
    const ws = btn.closest('.ws');
    if (!ws) return;
    const collapsed = ws.classList.toggle('is-collapsed');
    btn.textContent = collapsed ? '\u276F' : '\u276E';
    btn.title = collapsed ? t('expand') : t('collapse');
    try { localStorage.setItem('tc_collapsed_' + ws.id, collapsed ? '1' : '0'); } catch (e) { /* ignore */ }
    saveWorkspaceState();
}

function restoreSplitters() {
    ['translateWorkspace', 'writingWorkspace', 'speechWorkspace'].forEach(function (id) {
        const ws = document.getElementById(id);
        if (!ws) return;
        const left = ws.querySelector('.ws-left');
        let pct = NaN;
        try { pct = parseFloat(localStorage.getItem('tc_split_' + id) || ''); } catch (e) { pct = NaN; }
        if (left && !isNaN(pct) && pct > 0) left.style.flex = '0 0 ' + pct + '%';
        let collapsed = false;
        try { collapsed = localStorage.getItem('tc_collapsed_' + id) === '1'; } catch (e) { collapsed = false; }
        if (collapsed) {
            ws.classList.add('is-collapsed');
            const b = ws.querySelector('.ws-collapse');
            if (b) { b.textContent = '\u276F'; b.title = t('expand'); }
        }
    });
}

// =========================================================================
// Session history + workspace persistence
// =========================================================================
const HISTORY_KEY = 'tc_history';
const STATE_KEY = 'tc_state';

function loadHistory() {
    try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]') || []; } catch (e) { return []; }
}
function persistHistory(rows) {
    try { localStorage.setItem(HISTORY_KEY, JSON.stringify(rows.slice(0, 200))); } catch (e) { /* ignore */ }
}
function addHistoryRecord(rec) {
    const rows = loadHistory();
    rows.unshift(Object.assign({
        id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
        ts: Date.now(),
    }, rec));
    persistHistory(rows);
    renderHistory();
}
function deleteHistoryRecord(id) {
    persistHistory(loadHistory().filter(function (r) { return r.id !== id; }));
    renderHistory();
}
function clearHistory() {
    if (!confirm(t('clearAll') + '?')) return;
    localStorage.removeItem(HISTORY_KEY);
    renderHistory();
    track('history.clear', {});
}
function openHistory() {
    renderHistory();
    new bootstrap.Modal(document.getElementById('historyModal')).show();
}
function _fmtTime(ts) {
    try { return new Date(ts).toLocaleString(); } catch (e) { return ''; }
}
function renderHistory() {
    const box = document.getElementById('historyList');
    if (!box) return;
    const rows = loadHistory();
    if (!rows.length) {
        box.innerHTML = '<span class="muted">' + t('historyEmpty') + '</span>';
        return;
    }
    box.innerHTML = rows.map(function (r) {
        const kind = r.kind === 'writing' ? t('workspaceWriting') : t('workspaceTranslate');
        const src = (r.source || '').slice(0, 70);
        const out = r.kind === 'writing'
            ? ('✓ ' + (r.overall === null || r.overall === undefined ? '—' : r.overall))
            : Object.values(r.results || {}).join(' | ');
        return '<div class="history-row">' +
            '<div style="flex:1;min-width:0;">' +
            '<div><span class="badge bg-secondary me-1">' + kind + '</span>' +
            '<span class="muted">' + _fmtTime(r.ts) + '</span></div>' +
            '<div class="text-truncate">' + _esc(src) + '</div>' +
            '<div class="text-truncate muted">' + _esc(String(out).slice(0, 90)) + '</div>' +
            '</div>' +
            '<div class="text-nowrap">' +
            '<button class="btn btn-sm btn-link p-0 me-2" onclick="loadHistoryRecord(\'' + r.id + '\')">' + t('loadItem') + '</button>' +
            '<button class="btn btn-sm btn-link p-0" onclick="deleteHistoryRecord(\'' + r.id + '\')">' + t('deleteItem') + '</button>' +
            '</div></div>';
    }).join('');
}

function _findItemByLang(lang) {
    return Array.from(document.querySelectorAll('#translateWorkspace .target-lang-item')).find(function (it) {
        return it.querySelector('.target-lang-select').value === lang;
    });
}
function ensureTargetLang(lang) {
    if (_findItemByLang(lang)) return;
    addTargetLanguage();
    const items = document.querySelectorAll('#translateWorkspace .target-lang-item');
    const last = items[items.length - 1];
    if (last) last.querySelector('.target-lang-select').value = lang;
}

function loadHistoryRecord(id) {
    const rec = loadHistory().find(function (r) { return r.id === id; });
    if (!rec) return;
    const modalEl = document.getElementById('historyModal');
    const m = bootstrap.Modal.getInstance(modalEl);
    if (m) m.hide();

    if (rec.kind === 'writing') {
        switchWorkspace('writing');
        if (rec.prompt) {
            _writingPrompt = rec.prompt;
            const lvl = document.getElementById('writingLevel');
            const ttl = document.getElementById('writingTitle');
            const txt = document.getElementById('writingPromptText');
            if (lvl) lvl.textContent = rec.prompt.level || '';
            if (ttl) ttl.textContent = rec.prompt.title || '';
            if (txt) txt.textContent = rec.prompt.prompt || '';
        }
        const ta = document.getElementById('writingEssay');
        if (ta) {
            ta.value = rec.essay || '';
            const c = document.getElementById('writingCount');
            if (c) c.textContent = ta.value.length;
        }
    } else {
        switchWorkspace('translate');
        const src = document.getElementById('sourceText');
        if (src) {
            src.value = rec.source || '';
            document.getElementById('charCount').textContent = src.value.length;
        }
        if (rec.mode) document.getElementById('translationMode').value = rec.mode;
        Object.keys(rec.results || {}).forEach(function (lang) {
            ensureTargetLang(lang);
            const item = _findItemByLang(lang);
            if (item) item.querySelector('.translation-result').value = rec.results[lang];
        });
    }
    saveWorkspaceState();
}

function captureTranslationRecord(mode) {
    const results = {};
    document.querySelectorAll('#translateWorkspace .target-lang-item').forEach(function (it) {
        const lang = it.querySelector('.target-lang-select').value;
        const text = (it.querySelector('.translation-result').value || '').trim();
        if (text) results[lang] = text;
    });
    if (!Object.keys(results).length) return;
    addHistoryRecord({
        kind: 'translate',
        mode: mode,
        source: document.getElementById('sourceText').value,
        results: results,
        endpoint: currentEndpoint(),
    });
}

let _saveTimer = null;
function saveWorkspaceState() {
    clearTimeout(_saveTimer);
    _saveTimer = setTimeout(function () {
        try {
            const results = {};
            document.querySelectorAll('#translateWorkspace .target-lang-item').forEach(function (it) {
                results[it.querySelector('.target-lang-select').value] = it.querySelector('.translation-result').value;
            });
            const langs = Array.from(document.querySelectorAll('#translateWorkspace .target-lang-select')).map(function (s) { return s.value; });
            localStorage.setItem(STATE_KEY, JSON.stringify({
                source: document.getElementById('sourceText').value,
                sourceLang: document.getElementById('sourceLang').value,
                mode: document.getElementById('translationMode').value,
                langs: langs,
                results: results,
                essay: (document.getElementById('writingEssay') || {}).value || '',
                author: (document.getElementById('writingAuthor') || {}).value || '',
                workspace: (function () {
                    if ((document.getElementById('speechWorkspace') || {}).style.display !== 'none') return 'speech';
                    if ((document.getElementById('writingWorkspace') || {}).style.display !== 'none') return 'writing';
                    return 'translate';
                })(),
                prompt: _writingPrompt,
                speech: _speechPassage,
                writingLang: _writingLang,
                speechLang: _speechLang,
            }));
        } catch (e) { /* quota */ }
    }, 300);
}

function restoreWorkspaceState() {
    let st = null;
    try { st = JSON.parse(localStorage.getItem(STATE_KEY) || 'null'); } catch (e) { st = null; }
    if (!st) return;
    if (st.source) {
        document.getElementById('sourceText').value = st.source;
        document.getElementById('charCount').textContent = st.source.length;
    }
    if (st.sourceLang) document.getElementById('sourceLang').value = st.sourceLang;
    if (st.mode) document.getElementById('translationMode').value = st.mode;
    if (Array.isArray(st.langs) && st.langs.length) {
        while (document.querySelectorAll('#translateWorkspace .target-lang-item').length < st.langs.length) {
            addTargetLanguage();
        }
        const items = Array.from(document.querySelectorAll('#translateWorkspace .target-lang-item'));
        items.slice(st.langs.length).forEach(function (el) { el.remove(); });
        const selects = document.querySelectorAll('#translateWorkspace .target-lang-select');
        st.langs.forEach(function (lang, i) { if (selects[i]) selects[i].value = lang; });
        Object.entries(st.results || {}).forEach(function (entry) {
            const item = _findItemByLang(entry[0]);
            if (item) item.querySelector('.translation-result').value = entry[1] || '';
        });
    }
    if (st.essay) {
        const ta = document.getElementById('writingEssay');
        if (ta) {
            ta.value = st.essay;
            const c = document.getElementById('writingCount');
            if (c) c.textContent = ta.value.length;
        }
    }
    if (st.author) {
        const a = document.getElementById('writingAuthor');
        if (a) a.value = st.author;
    }
    if (st.prompt) {
        _writingPrompt = st.prompt;
        const lvl = document.getElementById('writingLevel');
        const ttl = document.getElementById('writingTitle');
        const txt = document.getElementById('writingPromptText');
        if (lvl) lvl.textContent = st.prompt.level || '';
        if (ttl) ttl.textContent = st.prompt.title || '';
        if (txt) txt.textContent = st.prompt.prompt || '';
    }
    if (st.writingLang) _writingLang = st.writingLang;
    if (st.speechLang) _speechLang = st.speechLang;
    if (st.speech) {
        _speechPassage = st.speech;
        const lvl = document.getElementById('speechLevel');
        const txt = document.getElementById('speechText');
        if (lvl) lvl.textContent = st.speech.level || '';
        if (txt) txt.textContent = st.speech.text || '';
    }
    toggleIterativeCountContainer();
    if (st.workspace === 'writing') switchWorkspace('writing');
    else if (st.workspace === 'speech') switchWorkspace('speech');
}

document.addEventListener('input', function (e) {
    if (e.target && (e.target.id === 'sourceText' || e.target.id === 'writingEssay' ||
        e.target.id === 'writingAuthor' || e.target.classList.contains('translation-result'))) {
        saveWorkspaceState();
    }
});
document.addEventListener('change', function (e) {
    if (e.target && (e.target.id === 'sourceLang' || e.target.id === 'translationMode' ||
        e.target.classList.contains('target-lang-select'))) {
        saveWorkspaceState();
    }
});

// =========================================================================
// Writing workspace (TCFL essay grading)
// =========================================================================
let _writingPrompt = null;
let _writingLang = 'zh';

function switchWorkspace(ws) {
    const map = { translate: 'translateWorkspace', writing: 'writingWorkspace', speech: 'speechWorkspace', reading: 'readingWorkspace' };
    Object.keys(map).forEach(function (k) {
        const el = document.getElementById(map[k]);
        if (el) el.style.display = (k === ws) ? '' : 'none';
    });
    [['wsTranslateBtn', 'translate'], ['wsWritingBtn', 'writing'], ['wsSpeechBtn', 'speech'], ['wsReadingBtn', 'reading']].forEach(function (pair) {
        const b = document.getElementById(pair[0]);
        if (!b) return;
        b.className = 'btn btn-sm ' + (pair[1] === ws ? 'btn-primary' : 'btn-outline-primary');
    });
    if (ws === 'writing' && !_writingPrompt) loadWritingPrompt();
    if (ws === 'speech' && !_speechPassage) loadSpeechPassage();
    if (ws === 'reading' && !_readingArticle) { loadReadingCatalog().then(loadReadingArticle); }
    track('workspace.switch', { workspace: ws });
}

async function loadWritingPrompt() {
    const levelEl = document.getElementById('writingLevel');
    const titleEl = document.getElementById('writingTitle');
    const textEl = document.getElementById('writingPromptText');
    try {
        const resp = await axios.get('/api/writing/prompt', { params: { lang: _writingLang } });
        _writingPrompt = resp.data.prompt || {};
        if (levelEl) levelEl.textContent = _writingPrompt.level || '';
        if (titleEl) titleEl.textContent = _writingPrompt.title || '';
        if (textEl) textEl.textContent = _writingPrompt.prompt || '';
        const g = document.getElementById('writingGradeResult');
        const p = document.getElementById('writingPolishResult');
        if (g) g.innerHTML = '';
        if (p) p.innerHTML = '';
        track('writing.new_prompt', { id: _writingPrompt.id, level: _writingPrompt.level });
    } catch (e) {
        if (textEl) textEl.innerHTML = '<span class="tc-error">' + (e.message || '') + '</span>';
    }
}

function _writingScoresHtml(g) {
    const dims = {
        content: 'dimContent', organization: 'dimOrganization', grammar: 'dimGrammar',
        vocabulary: 'dimVocabulary', coherence: 'dimCoherence',
    };
    let html = '<div class="d-flex gap-2 flex-wrap mb-2">';
    html += '<div class="score-chip overall"><span class="value">' +
        (g.overall === null || g.overall === undefined ? '—' : g.overall) +
        '</span><span class="label">' + t('total') + '</span></div>';
    Object.entries(g.scores || {}).forEach(function (kv) {
        html += '<div class="score-chip"><span class="value">' + kv[1] +
            '</span><span class="label">' + t(dims[kv[0]] || kv[0]) + '</span></div>';
    });
    html += '</div>';
    if (g.level) {
        html += '<div class="mb-2"><span class="badge bg-secondary">' + _esc(g.level) + '</span></div>';
    }
    return html;
}

function renderWritingGrade(g) {
    const box = document.getElementById('writingGradeResult');
    if (!box) return;
    if (g.error) {
        box.innerHTML = '<span class="tc-error">' + _esc(g.error) + '</span>';
        return;
    }
    let html = _writingScoresHtml(g);
    html += (g.issues || []).map(function (i) {
        return '<div class="issue-row"><span class="tag">' + _esc(i.type) + '</span><div>' +
            '<div>' + _esc(i.span || '') + '</div>' +
            '<div class="muted">' + _esc(i.advice || '') + '</div></div></div>';
    }).join('');
    if (g.comment) {
        html += '<div class="mt-2" style="white-space:pre-wrap;">' + _esc(g.comment) + '</div>';
    }
    box.innerHTML = html;
}

async function writingGrade() {
    const essay = (document.getElementById('writingEssay') || {}).value || '';
    const box = document.getElementById('writingGradeResult');
    if (!essay.trim()) {
        box.innerHTML = '<span class="tc-error">' + t('missingText') + '</span>';
        return;
    }
    box.innerHTML = '<span class="muted">' + t('grading') + '</span>';
    try {
        const resp = await axios.post('/api/writing/grade', {
            prompt: (_writingPrompt || {}).prompt || '',
            essay: essay,
            lang: _writingLang,
            endpoint: currentReviewerEndpoint(),
            model: currentReviewerModel() || undefined,
            author: (document.getElementById('writingAuthor') || {}).value || undefined,
        }, { timeout: 240000 });
        renderWritingGrade(resp.data.grade || {});
        if (resp.data.submission_id) {
            document.getElementById('writingHint').textContent =
                t('saved') + ' #' + resp.data.submission_id;
        }
        addHistoryRecord({
            kind: 'writing', source: (_writingPrompt || {}).title || (_writingPrompt || {}).prompt || '',
            prompt: _writingPrompt, essay: essay, overall: (resp.data.grade || {}).overall,
        });
        saveWorkspaceState();
        track('writing.grade', { overall: (resp.data.grade || {}).overall });
    } catch (e) {
        const timedOut = e.code === 'ECONNABORTED' || /timeout/i.test(e.message || '');
        box.innerHTML = '<span class="tc-error">' + (timedOut ? t('gradeTimeout') :
            ((e.response && e.response.data && e.response.data.error) || e.message)) + '</span>';
    }
}

function renderWritingPolish(p) {
    const box = document.getElementById('writingPolishResult');
    if (!box) return;
    if (!p.parse_ok) {
        box.innerHTML = '<span class="tc-error">' + _esc(p.error || '') + '</span>' +
            (p.polished ? '<div class="mt-1" style="white-space:pre-wrap;">' + _esc(p.polished) + '</div>' : '');
        return;
    }
    const edits = (p.edits || []).map(function (e) {
        return '<div class="edit-row"><span class="tag">' + _esc(e.type) + '</span><div>' +
            '<div><s class="muted">' + _esc(e.original || '') + '</s> → ' + _esc(e.revised || '') + '</div>' +
            '<div class="muted">' + _esc(e.reason || '') + '</div></div></div>';
    }).join('');
    box.innerHTML =
        '<div class="card"><div class="card-header py-2">' + t('polish') + '</div>' +
        '<div class="card-body py-2"><div id="writingPolishedText" style="white-space:pre-wrap;line-height:1.7;">' +
        _esc(p.polished || '') + '</div>' +
        (p.summary ? '<div class="muted mt-1">' + _esc(p.summary) + '</div>' : '') +
        '<button class="btn btn-sm btn-light mt-2" onclick="applyWritingPolish()">' + t('applyPolish') + '</button>' +
        '</div></div>' + (edits ? '<div class="mt-2">' + edits + '</div>' : '');
}

function applyWritingPolish() {
    const el = document.getElementById('writingPolishedText');
    const ta = document.getElementById('writingEssay');
    if (!el || !ta) return;
    ta.value = el.textContent;
    document.getElementById('writingCount').textContent = ta.value.length;
    document.getElementById('writingHint').textContent = '';
}

async function writingPolish() {
    const essay = (document.getElementById('writingEssay') || {}).value || '';
    const box = document.getElementById('writingPolishResult');
    if (!essay.trim()) {
        box.innerHTML = '<span class="tc-error">' + t('missingText') + '</span>';
        return;
    }
    box.innerHTML = '<span class="muted">' + t('polishing') + '</span>';
    try {
        const resp = await axios.post('/api/writing/polish', {
            prompt: (_writingPrompt || {}).prompt || '',
            essay: essay,
            lang: _writingLang,
            endpoint: currentReviewerEndpoint(),
            model: currentReviewerModel() || undefined,
            author: (document.getElementById('writingAuthor') || {}).value || undefined,
        }, { timeout: 240000 });
        renderWritingPolish(resp.data.polish || {});
        track('writing.polish', { edits: ((resp.data.polish || {}).edits || []).length });
    } catch (e) {
        const timedOut = e.code === 'ECONNABORTED' || /timeout/i.test(e.message || '');
        box.innerHTML = '<span class="tc-error">' + (timedOut ? t('polishTimeout') :
            ((e.response && e.response.data && e.response.data.error) || e.message)) + '</span>';
    }
}

function copyWriting() {
    const ta = document.getElementById('writingEssay');
    if (!ta) return;
    navigator.clipboard.writeText(ta.value);
}

document.addEventListener('DOMContentLoaded', function () {
    restoreSplitters();
    restoreWorkspaceState();
    const ta = document.getElementById('writingEssay');
    if (ta) {
        ta.addEventListener('input', function () {
            document.getElementById('writingCount').textContent = this.value.length;
        });
    }
    const gradeBtn = document.getElementById('writingGradeResult');
    if (gradeBtn) gradeBtn.innerHTML = '';
});

document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('#translateWorkspace .target-lang-item').forEach(function (it) {
        const ta = it.querySelector('.translation-result');
        if (ta && ta.value.trim()) it.dataset.reference = ta.value;
    });
    track('page.view', {});
});


// =========================================================================
// Multilingual extensions (speech: zh/en/ja annotations + diagnosis;
// writing: language switch). Later declarations override the base ones.
// =========================================================================
let _speechLang = 'zh';
let _lastSpeech = null;
let _annoKind = null;

function onWritingLangChange() {
    const sel = document.getElementById('writingLang');
    _writingLang = (sel && sel.value) || 'zh';
    loadWritingPrompt();
    saveWorkspaceState();
}

function onSpeechLangChange() {
    const sel = document.getElementById('speechLang');
    _speechLang = (sel && sel.value) || 'zh';
    _lastSpeech = null;
    _annoKind = null;
    const box = document.getElementById('speechResult');
    if (box) box.innerHTML = '';
    const diag = document.getElementById('diagnoseBtn');
    if (diag) diag.style.display = 'none';
    loadSpeechPassage();
    saveWorkspaceState();
}

async function loadSpeechPassage() {
    try {
        const resp = await axios.get('/api/speech/passage', { params: { lang: _speechLang } });
        _speechPassage = resp.data.passage || {};
        const level = document.getElementById('speechLevel');
        const text = document.getElementById('speechText');
        if (level) level.textContent = _speechPassage.level || '';
        if (text) text.textContent = _speechPassage.text || '';
        const audio = document.getElementById('speechAudio');
        if (audio) { audio.pause(); audio.removeAttribute('src'); audio.style.display = 'none'; }
        const dl = document.getElementById('speechDownload');
        if (dl) dl.style.display = 'none';
        const ann = document.getElementById('speechAnnotation');
        if (ann) ann.innerHTML = '';
        _annoKind = null;
        renderSpeechAnnoButtons();
        saveWorkspaceState();
    } catch (e) {
        const text = document.getElementById('speechText');
        if (text) text.innerHTML = '<span class="tc-error">' + (e.message || '') + '</span>';
    }
}

function renderSpeechAnnoButtons() {
    const box = document.getElementById('speechAnnoBtns');
    if (!box) return;
    const kinds = _speechLang === 'zh' ? ['pinyin']
        : _speechLang === 'en' ? ['ipa']
        : ['romaji', 'hiragana', 'katakana'];
    box.innerHTML = kinds.map(function (k) {
        return '<button class="btn btn-sm ' + (_annoKind === k ? 'btn-primary' : 'btn-outline-secondary') +
            '" onclick="toggleSpeechAnno(\'' + k + '\')">' + t(k) + '</button>';
    }).join('');
}

async function toggleSpeechAnno(kind) {
    const ann = document.getElementById('speechAnnotation');
    if (!ann) return;
    if (_annoKind === kind) {
        _annoKind = null;
        ann.innerHTML = '';
        renderSpeechAnnoButtons();
        return;
    }
    const text = (_speechPassage || {}).text || '';
    try {
        const resp = await axios.post('/api/speech/annotate', { text: text, lang: _speechLang }, { timeout: 60000 });
        _annoKind = kind;
        renderSpeechAnnoButtons();
        renderSpeechAnnotation(resp.data.annotation || {}, kind);
    } catch (e) {
        ann.innerHTML = '<span class="tc-error">' + (e.message || '') + '</span>';
    }
}

function renderSpeechAnnotation(anno, kind) {
    const box = document.getElementById('speechAnnotation');
    if (!box) return;
    const tokens = anno.tokens || [];
    box.innerHTML = tokens.map(function (tk) {
        const txt = _esc(tk.text || '');
        const val = kind === 'pinyin' ? (tk.pinyin || '')
            : kind === 'ipa' ? (tk.ipa || '')
            : kind === 'romaji' ? (tk.romaji || '')
            : kind === 'hiragana' ? (tk.hira || '')
            : (tk.kata || '');
        if (!val) return txt;
        return '<ruby>' + txt + '<rt>' + _esc(val) + '</rt></ruby>';
    }).join('');
}

async function speechTTS() {
    const text = (_speechPassage || {}).text || '';
    const hint = document.getElementById('speechTTSHint');
    const audio = document.getElementById('speechAudio');
    if (!text.trim()) return;
    if (hint) hint.textContent = t('computing');
    try {
        const resp = await axios.post('/api/speech/tts', { text: text, lang: _speechLang }, { timeout: 180000 });
        if (audio) { audio.src = resp.data.url; audio.style.display = ''; audio.play().catch(function () {}); }
        const dl = document.getElementById('speechDownload');
        if (dl) { dl.href = resp.data.url; dl.download = (resp.data.audio || {}).file || 'reference.m4a'; dl.style.display = ''; }
        if (hint) hint.textContent = (resp.data.audio || {}).voice || '';
        track('speech.tts', { chars: text.length, lang: _speechLang });
    } catch (e) {
        if (hint) hint.textContent = (e.response && e.response.data && e.response.data.error) || e.message;
    }
}

async function onRecordingStop() {
    const btn = document.getElementById('recordBtn');
    if (btn) { btn.textContent = t('record'); btn.className = 'btn btn-sm btn-primary'; }
    const blob = new Blob(_recChunks, { type: 'audio/webm' });
    const audio = document.getElementById('recordAudio');
    if (audio) { audio.src = URL.createObjectURL(blob); audio.style.display = ''; }
    const box = document.getElementById('speechResult');
    if (box) box.innerHTML = '<span class="muted">' + t('grading') + '</span>';
    const target = (_speechPassage || {}).text || '';
    const fd = new FormData();
    fd.append('file', blob, 'rec.webm');
    fd.append('target_text', target);
    fd.append('language', _speechLang);
    try {
        const resp = await axios.post('/api/speech/score', fd, { timeout: 300000 });
        const r = resp.data.result || {};
        _lastSpeech = { target: target, transcript: r.transcript || '', items: r.items || [] };
        renderSpeechScore(r, target);
        const diag = document.getElementById('diagnoseBtn');
        if (diag) diag.style.display = '';
    } catch (e) {
        if (box) box.innerHTML = '<span class="tc-error">' +
            ((e.response && e.response.data && e.response.data.error) || e.message) + '</span>';
    }
}

async function speechDiagnose() {
    if (!_lastSpeech) return;
    const diag = document.getElementById('diagnoseBtn');
    if (diag) diag.disabled = true;
    const box = document.getElementById('speechResult');
    try {
        const resp = await axios.post('/api/speech/diagnose', {
            target_text: _lastSpeech.target,
            transcript: _lastSpeech.transcript,
            items: _lastSpeech.items,
            language: _speechLang,
            endpoint: currentReviewerEndpoint(),
            model: currentReviewerModel() || undefined,
        }, { timeout: 240000 });
        const d = resp.data.diagnosis || {};
        let html = '<div class="mt-2"><div class="fw-semibold mb-1">' + t('diagnosis') + '</div>';
        if (d.summary) html += '<div class="muted mb-2" style="white-space:pre-wrap;">' + _esc(d.summary) + '</div>';
        html += (d.issues || []).map(function (i) {
            return '<div class="issue-row"><span class="tag">' + _esc(i.span || '') + '</span><div>' +
                '<div>' + _esc(i.problem || '') + '</div>' +
                '<div class="muted">' + _esc(i.advice || '') + '</div></div></div>';
        }).join('');
        if (!d.parse_ok) html += '<div class="tc-error">' + _esc(d.error || '') + '</div>';
        html += '</div>';
        if (box) box.insertAdjacentHTML('beforeend', html);
        track('speech.diagnose', { issues: (d.issues || []).length, lang: _speechLang });
    } catch (e) {
        if (box) box.insertAdjacentHTML('beforeend', '<div class="tc-error">' +
            ((e.response && e.response.data && e.response.data.error) || e.message) + '</div>');
    } finally {
        if (diag) diag.disabled = false;
    }
}

// restore the chosen languages on load
document.addEventListener('DOMContentLoaded', function () {
    const rs = document.getElementById('reviewStrategy');
    if (rs) {
        const saved = localStorage.getItem('tc_review_strategy');
        if (saved) rs.value = saved;
        rs.addEventListener('change', function () {
            localStorage.setItem('tc_review_strategy', this.value);
        });
    }
    const wl = document.getElementById('writingLang');
    if (wl) wl.value = _writingLang;
    const sl = document.getElementById('speechLang');
    if (sl) { sl.value = _speechLang; renderSpeechAnnoButtons(); }
});
