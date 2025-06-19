// 术语库管理页面的JavaScript

// 全局变量
let currentPage = 1;
let perPage = 50;
let currentSearch = '';
let currentEditTerm = '';

// 页面加载完成时初始化
document.addEventListener('DOMContentLoaded', function() {
    loadStatistics();
    loadTerms();
    
    // 绑定回车搜索事件
    document.getElementById('searchInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            searchTerms();
        }
    });
});

// 加载统计信息
async function loadStatistics() {
    try {
        const response = await axios.get('/api/terminology/stats');
        const stats = response.data;
        
        document.getElementById('totalTerms').textContent = stats.total_terms || 0;
        
        // 显示语言分布
        const languageStatsDiv = document.getElementById('languageStats');
        languageStatsDiv.innerHTML = '';
        
        if (stats.most_common_languages && stats.most_common_languages.length > 0) {
            stats.most_common_languages.forEach(([lang, count]) => {
                const badge = document.createElement('span');
                badge.className = 'badge bg-secondary me-2 mb-1';
                badge.textContent = `${getLanguageName(lang)}: ${count}`;
                languageStatsDiv.appendChild(badge);
            });
        } else {
            languageStatsDiv.innerHTML = '<span class="text-muted">暂无数据</span>';
        }
        
    } catch (error) {
        console.error('Failed to load statistics:', error);
    }
}

// 加载术语列表
async function loadTerms() {
    showLoading(true);
    
    try {
        const response = await axios.get('/api/terminology/list', {
            params: {
                page: currentPage,
                per_page: perPage,
                search: currentSearch
            }
        });
        
        const data = response.data;
        
        if (data.success) {
            displayTerms(data.terms);
            displayPagination(data.pagination);
        } else {
            showError('加载术语失败: ' + data.error);
        }
        
    } catch (error) {
        showError('加载术语失败: ' + error.message);
    } finally {
        showLoading(false);
    }
}

// 显示术语列表
function displayTerms(terms) {
    const tbody = document.getElementById('termsTableBody');
    tbody.innerHTML = '';
    
    if (terms.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted">没有找到术语</td></tr>';
        return;
    }
    
    terms.forEach(termData => {
        const row = document.createElement('tr');
        
        // 术语列
        const termCell = document.createElement('td');
        termCell.innerHTML = `<strong>${escapeHtml(termData.term)}</strong>`;
        
        // 翻译列
        const translationsCell = document.createElement('td');
        const translationsHtml = Object.entries(termData.translations)
            .map(([lang, translation]) => 
                `<span class="badge bg-light text-dark me-1 mb-1">${getLanguageName(lang)}: ${escapeHtml(translation)}</span>`
            ).join('');
        translationsCell.innerHTML = translationsHtml;
        
        // 操作列
        const actionsCell = document.createElement('td');
        actionsCell.innerHTML = `
            <button class="btn btn-sm btn-primary me-1" onclick="editTerm('${escapeHtml(termData.term)}')">
                <i class="bi bi-pencil"></i> 编辑
            </button>
            <button class="btn btn-sm btn-danger" onclick="deleteTerm('${escapeHtml(termData.term)}')">
                <i class="bi bi-trash"></i> 删除
            </button>
        `;
        
        row.appendChild(termCell);
        row.appendChild(translationsCell);
        row.appendChild(actionsCell);
        tbody.appendChild(row);
    });
}

// 显示分页
function displayPagination(pagination) {
    const paginationUl = document.getElementById('pagination');
    paginationUl.innerHTML = '';
    
    if (pagination.pages <= 1) return;
    
    // 上一页
    if (pagination.page > 1) {
        const prevLi = document.createElement('li');
        prevLi.className = 'page-item';
        prevLi.innerHTML = `<a class="page-link" href="javascript:void(0)" onclick="goToPage(${pagination.page - 1})">上一页</a>`;
        paginationUl.appendChild(prevLi);
    }
    
    // 页码
    const startPage = Math.max(1, pagination.page - 2);
    const endPage = Math.min(pagination.pages, pagination.page + 2);
    
    for (let i = startPage; i <= endPage; i++) {
        const li = document.createElement('li');
        li.className = `page-item ${i === pagination.page ? 'active' : ''}`;
        li.innerHTML = `<a class="page-link" href="javascript:void(0)" onclick="goToPage(${i})">${i}</a>`;
        paginationUl.appendChild(li);
    }
    
    // 下一页
    if (pagination.page < pagination.pages) {
        const nextLi = document.createElement('li');
        nextLi.className = 'page-item';
        nextLi.innerHTML = `<a class="page-link" href="javascript:void(0)" onclick="goToPage(${pagination.page + 1})">下一页</a>`;
        paginationUl.appendChild(nextLi);
    }
}

// 搜索术语
function searchTerms() {
    currentSearch = document.getElementById('searchInput').value;
    currentPage = 1;
    loadTerms();
}

// 改变每页显示数量
function changePageSize() {
    perPage = parseInt(document.getElementById('perPageSelect').value);
    currentPage = 1;
    loadTerms();
}

// 跳转到指定页面
function goToPage(page) {
    currentPage = page;
    loadTerms();
}

// 显示添加术语模态框
function showAddTermModal() {
    document.getElementById('newTermInput').value = '';
    document.getElementById('translationsContainer').innerHTML = `
        <div class="row mb-2">
            <div class="col-3">
                <select class="form-select translation-lang" aria-label="选择语言">
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
            <div class="col-8">
                <input type="text" class="form-control translation-text" placeholder="翻译">
            </div>
            <div class="col-1">
                <button type="button" class="btn btn-sm btn-danger" onclick="removeTranslationRow(this)" aria-label="删除此翻译行">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
        </div>
    `;
    
    const modal = new bootstrap.Modal(document.getElementById('addTermModal'));
    modal.show();
}

// 添加翻译行
function addTranslationRow() {
    const container = document.getElementById('translationsContainer');
    const newRow = document.createElement('div');
    newRow.className = 'row mb-2';
    newRow.innerHTML = `
        <div class="col-3">
            <select class="form-select translation-lang" aria-label="选择语言">
                <option value="zh-cn">中文大陆地区现代文简体</option>
                <option value="zh-tw">中文港澳台地区现代文繁体</option>
                <option value="zh-classical-cn">中文文言文简体</option>
                <option value="zh-classical-tw">中文文言文繁体</option>
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
        <div class="col-8">
            <input type="text" class="form-control translation-text" placeholder="翻译">
        </div>
        <div class="col-1">
            <button type="button" class="btn btn-sm btn-danger" onclick="removeTranslationRow(this)" aria-label="删除此翻译行">
                <i class="bi bi-trash"></i>
            </button>
        </div>
    `;
    container.appendChild(newRow);
}

// 删除翻译行
function removeTranslationRow(button) {
    const container = button.closest('#translationsContainer') || button.closest('#editTranslationsContainer');
    if (container.children.length > 1) {
        button.closest('.row').remove();
    } else {
        alert('至少需要保留一个翻译');
    }
}

// 保存术语
async function saveTerm() {
    const term = document.getElementById('newTermInput').value.trim();
    if (!term) {
        alert('请输入术语');
        return;
    }
    
    const translations = {};
    document.querySelectorAll('#translationsContainer .row').forEach(row => {
        const lang = row.querySelector('.translation-lang').value;
        const translation = row.querySelector('.translation-text').value.trim();
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
        
        if (response.data.success) {
            showSuccess('术语添加成功');
            bootstrap.Modal.getInstance(document.getElementById('addTermModal')).hide();
            loadStatistics();
            loadTerms();
        } else {
            showError('添加失败: ' + response.data.error);
        }
        
    } catch (error) {
        showError('添加失败: ' + error.message);
    }
}

// 编辑术语
function editTerm(term) {
    currentEditTerm = term;
    
    // 从表格中获取术语数据
    const rows = document.querySelectorAll('#termsTableBody tr');
    let termData = null;
    
    for (const row of rows) {
        const termCell = row.cells[0];
        if (termCell.textContent.trim() === term) {
            // 解析翻译数据
            const badges = row.cells[1].querySelectorAll('.badge');
            const translations = {};
            badges.forEach(badge => {
                const text = badge.textContent;
                const colonIndex = text.indexOf(':');
                if (colonIndex > 0) {
                    const langName = text.substring(0, colonIndex).trim();
                    const translation = text.substring(colonIndex + 1).trim();
                    const langCode = getLanguageCode(langName);
                    if (langCode) {
                        translations[langCode] = translation;
                    }
                }
            });
            termData = { term, translations };
            break;
        }
    }
    
    if (!termData) {
        showError('找不到术语数据');
        return;
    }
    
    // 填充编辑表单
    document.getElementById('editTermInput').value = term;
    
    const container = document.getElementById('editTranslationsContainer');
    container.innerHTML = '';
    
    Object.entries(termData.translations).forEach(([lang, translation]) => {
        addEditTranslationRow(lang, translation);
    });
    
    const modal = new bootstrap.Modal(document.getElementById('editTermModal'));
    modal.show();
}

// 添加编辑翻译行
function addEditTranslationRow(selectedLang = 'en', translationText = '') {
    const container = document.getElementById('editTranslationsContainer');
    const newRow = document.createElement('div');
    newRow.className = 'row mb-2';
    newRow.innerHTML = `
        <div class="col-3">
            <select class="form-select translation-lang" aria-label="选择语言">
                <option value="zh-cn" ${selectedLang === 'zh-cn' ? 'selected' : ''}>中文大陆地区现代文简体</option>
                <option value="zh-tw" ${selectedLang === 'zh-tw' ? 'selected' : ''}>中文港澳台地区现代文繁体</option>
                <option value="zh-classical-cn" ${selectedLang === 'zh-classical-cn' ? 'selected' : ''}>中文文言文简体</option>
                <option value="zh-classical-tw" ${selectedLang === 'zh-classical-tw' ? 'selected' : ''}>中文文言文繁体</option>
                <option value="en" ${selectedLang === 'en' ? 'selected' : ''}>English</option>
                <option value="ja" ${selectedLang === 'ja' ? 'selected' : ''}>日本語</option>
                <option value="ko" ${selectedLang === 'ko' ? 'selected' : ''}>한국어</option>
                <option value="es" ${selectedLang === 'es' ? 'selected' : ''}>Español</option>
                <option value="fr" ${selectedLang === 'fr' ? 'selected' : ''}>Français</option>
                <option value="de" ${selectedLang === 'de' ? 'selected' : ''}>Deutsch</option>
                <option value="ru" ${selectedLang === 'ru' ? 'selected' : ''}>Русский</option>
                <option value="ar" ${selectedLang === 'ar' ? 'selected' : ''}>العربية</option>
                <option value="pt" ${selectedLang === 'pt' ? 'selected' : ''}>Português</option>
            </select>
        </div>
        <div class="col-8">
            <input type="text" class="form-control translation-text" placeholder="翻译" value="${escapeHtml(translationText)}">
        </div>
        <div class="col-1">
            <button type="button" class="btn btn-sm btn-danger" onclick="removeTranslationRow(this)" aria-label="删除此翻译行">
                <i class="bi bi-trash"></i>
            </button>
        </div>
    `;
    container.appendChild(newRow);
}

// 更新术语
async function updateTerm() {
    const translations = {};
    document.querySelectorAll('#editTranslationsContainer .row').forEach(row => {
        const lang = row.querySelector('.translation-lang').value;
        const translation = row.querySelector('.translation-text').value.trim();
        if (translation) {
            translations[lang] = translation;
        }
    });
    
    if (Object.keys(translations).length === 0) {
        alert('请至少添加一个翻译');
        return;
    }
    
    try {
        const response = await axios.put('/api/terminology/update', {
            term: currentEditTerm,
            translations: translations
        });
        
        if (response.data.success) {
            showSuccess('术语更新成功');
            bootstrap.Modal.getInstance(document.getElementById('editTermModal')).hide();
            loadTerms();
        } else {
            showError('更新失败: ' + response.data.error);
        }
        
    } catch (error) {
        showError('更新失败: ' + error.message);
    }
}

// 删除术语
async function deleteTerm(term) {
    if (!confirm(`确定要删除术语 "${term}" 吗？`)) {
        return;
    }
    
    try {
        const response = await axios.delete('/api/terminology/delete', {
            data: { term: term }
        });
        
        if (response.data.success) {
            showSuccess('术语删除成功');
            loadStatistics();
            loadTerms();
        } else {
            showError('删除失败: ' + response.data.error);
        }
        
    } catch (error) {
        showError('删除失败: ' + error.message);
    }
}

// 显示导入模态框
function showImportModal() {
    document.getElementById('importFile').value = '';
    const modal = new bootstrap.Modal(document.getElementById('importModal'));
    modal.show();
}

// 导入术语库
async function importTerminology() {
    const fileInput = document.getElementById('importFile');
    const file = fileInput.files[0];
    
    if (!file) {
        alert('请选择文件');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await axios.post('/api/terminology/upload', formData);
        
        if (response.data.success || response.data.imported !== undefined) {
            showSuccess(`成功导入 ${response.data.imported} 个术语`);
            bootstrap.Modal.getInstance(document.getElementById('importModal')).hide();
            loadStatistics();
            loadTerms();
        } else {
            showError('导入失败: ' + response.data.error);
        }
        
    } catch (error) {
        showError('导入失败: ' + error.message);
    }
}

// 导出术语库
async function exportTerminology() {
    const format = prompt('请选择导出格式 (csv/xlsx/tbx/json):', 'csv');
    if (!format) return;
    
    if (!['csv', 'xlsx', 'tbx', 'json'].includes(format.toLowerCase())) {
        alert('不支持的格式');
        return;
    }
    
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
        window.URL.revokeObjectURL(url);
        
    } catch (error) {
        showError('导出失败: ' + error.message);
    }
}

// 工具函数
function getLanguageName(code) {
    const names = {
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
    return names[code] || code;
}

function getLanguageCode(name) {
    const codes = {
        '中文大陆地区现代文简体': 'zh-cn',
        '中文港澳台地区现代文繁体': 'zh-tw',
        '中文文言文简体': 'zh-classical-cn',
        '中文文言文繁体': 'zh-classical-tw',
        'English': 'en',
        '日本語': 'ja',
        '한국어': 'ko',
        'Español': 'es',
        'Français': 'fr',
        'Deutsch': 'de',
        'Русский': 'ru',
        'العربية': 'ar',
        'Português': 'pt'
    };
    return codes[name] || null;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showLoading(show) {
    const indicator = document.getElementById('loadingIndicator');
    if (indicator) {
        indicator.style.display = show ? 'block' : 'none';
    }
}

function showSuccess(message) {
    // 可以使用更好的通知组件，这里简单使用alert
    alert(message);
}

function showError(message) {
    alert('错误: ' + message);
} 