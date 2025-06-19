// 翻译记忆库管理页面的JavaScript

// 全局变量
let currentPage = 1;
let perPage = 50;
let currentSearch = '';

// 页面加载完成时初始化
document.addEventListener('DOMContentLoaded', function() {
    loadStatistics();
    loadTranslations();
    
    // 绑定回车搜索事件
    document.getElementById('searchInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            searchTranslations();
        }
    });
});

// 加载统计信息
async function loadStatistics() {
    try {
        const response = await axios.get('/api/vector-db/stats');
        const stats = response.data;
        
        document.getElementById('totalItems').textContent = stats.total_items || 0;
        document.getElementById('indexSize').textContent = stats.index_size || 0;
        document.getElementById('avgLength').textContent = stats.avg_source_length || 0;
        
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

// 加载翻译记忆库列表
async function loadTranslations() {
    showLoading(true);
    
    try {
        const response = await axios.get('/api/vector-db/list', {
            params: {
                page: currentPage,
                per_page: perPage,
                search: currentSearch
            }
        });
        
        const data = response.data;
        
        if (data.success) {
            displayTranslations(data.items);
            displayPagination(data.pagination);
        } else {
            showError('加载翻译记忆库失败: ' + data.error);
        }
        
    } catch (error) {
        showError('加载翻译记忆库失败: ' + error.message);
    } finally {
        showLoading(false);
    }
}

// 显示翻译记忆库列表
function displayTranslations(items) {
    const tbody = document.getElementById('translationsTableBody');
    tbody.innerHTML = '';
    
    if (items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted">没有找到翻译记忆</td></tr>';
        return;
    }
    
    items.forEach(item => {
        const row = document.createElement('tr');
        
        // 源文本列
        const sourceCell = document.createElement('td');
        const sourceText = item.source.length > 100 ? 
            item.source.substring(0, 100) + '...' : item.source;
        sourceCell.innerHTML = `<div title="${escapeHtml(item.source)}">${escapeHtml(sourceText)}</div>`;
        
        // 翻译列
        const translationsCell = document.createElement('td');
        const translationsHtml = Object.entries(item.translations)
            .map(([lang, translation]) => {
                const shortTranslation = translation.length > 80 ? 
                    translation.substring(0, 80) + '...' : translation;
                return `<div class="mb-1"><span class="badge bg-info me-1">${getLanguageName(lang)}</span>${escapeHtml(shortTranslation)}</div>`;
            }).join('');
        translationsCell.innerHTML = translationsHtml;
        
        // 操作列
        const actionsCell = document.createElement('td');
        actionsCell.innerHTML = `
            <button class="btn btn-sm btn-info me-1" onclick="viewDetail(${item.index})">
                <i class="bi bi-eye"></i> 查看
            </button>
            <button class="btn btn-sm btn-danger" onclick="deleteTranslation(${item.index})">
                <i class="bi bi-trash"></i> 删除
            </button>
        `;
        
        row.appendChild(sourceCell);
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

// 搜索翻译
function searchTranslations() {
    currentSearch = document.getElementById('searchInput').value;
    currentPage = 1;
    loadTranslations();
}

// 改变每页显示数量
function changePageSize() {
    perPage = parseInt(document.getElementById('perPageSelect').value);
    currentPage = 1;
    loadTranslations();
}

// 跳转到指定页面
function goToPage(page) {
    currentPage = page;
    loadTranslations();
}

// 查看翻译详情
function viewDetail(index) {
    // 从表格中获取详细信息
    const rows = document.querySelectorAll('#translationsTableBody tr');
    const row = rows[index % perPage]; // 获取当前页面中的相对索引
    
    if (row) {
        const sourceText = row.cells[0].getAttribute('title') || row.cells[0].textContent;
        document.getElementById('detailSourceText').textContent = sourceText;
        
        // 解析翻译信息
        const translationsDiv = document.getElementById('detailTranslations');
        translationsDiv.innerHTML = '';
        
        const translationDivs = row.cells[1].querySelectorAll('div');
        translationDivs.forEach(div => {
            if (div.textContent.trim()) {
                const detailDiv = document.createElement('div');
                detailDiv.className = 'mb-2 p-2 border rounded';
                detailDiv.innerHTML = div.innerHTML;
                translationsDiv.appendChild(detailDiv);
            }
        });
        
        const modal = new bootstrap.Modal(document.getElementById('detailModal'));
        modal.show();
    }
}

// 删除翻译记忆
async function deleteTranslation(index) {
    if (!confirm('确定要删除这条翻译记忆吗？')) {
        return;
    }
    
    try {
        const response = await axios.delete('/api/vector-db/delete', {
            data: { index: index }
        });
        
        if (response.data.success) {
            showSuccess('翻译记忆删除成功');
            loadStatistics();
            loadTranslations();
        } else {
            showError('删除失败: ' + response.data.error);
        }
        
    } catch (error) {
        showError('删除失败: ' + error.message);
    }
}

// 显示智能搜索模态框
function showSearchModal() {
    document.getElementById('smartSearchInput').value = '';
    document.getElementById('smartSearchResults').innerHTML = '';
    const modal = new bootstrap.Modal(document.getElementById('searchModal'));
    modal.show();
}

// 执行智能搜索
async function performSmartSearch() {
    const query = document.getElementById('smartSearchInput').value.trim();
    const count = parseInt(document.getElementById('searchResultsCount').value);
    
    if (!query) {
        alert('请输入搜索查询');
        return;
    }
    
    const resultsDiv = document.getElementById('smartSearchResults');
    resultsDiv.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"></div></div>';
    
    try {
        const response = await axios.post('/api/vector-db/search', {
            query: query,
            k: count
        });
        
        const results = response.data;
        displaySmartSearchResults(results);
        
    } catch (error) {
        resultsDiv.innerHTML = `<div class="alert alert-danger">搜索失败: ${error.message}</div>`;
    }
}

// 显示智能搜索结果
function displaySmartSearchResults(results) {
    const resultsDiv = document.getElementById('smartSearchResults');
    resultsDiv.innerHTML = '';
    
    if (Object.keys(results).length === 0) {
        resultsDiv.innerHTML = '<div class="alert alert-info">没有找到相似的翻译</div>';
        return;
    }
    
    Object.entries(results).forEach(([lang, translations]) => {
        const langDiv = document.createElement('div');
        langDiv.className = 'mb-3';
        langDiv.innerHTML = `<h6><span class="badge bg-primary">${getLanguageName(lang)}</span></h6>`;
        
        const listDiv = document.createElement('div');
        listDiv.className = 'list-group';
        
        translations.forEach(item => {
            const itemDiv = document.createElement('div');
            itemDiv.className = 'list-group-item';
            itemDiv.innerHTML = `
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <div class="mb-1"><strong>源文本:</strong> ${escapeHtml(item.source)}</div>
                        <div><strong>翻译:</strong> ${escapeHtml(item.translation)}</div>
                    </div>
                    <span class="badge bg-success rounded-pill">${(item.similarity * 100).toFixed(1)}%</span>
                </div>
            `;
            listDiv.appendChild(itemDiv);
        });
        
        langDiv.appendChild(listDiv);
        resultsDiv.appendChild(langDiv);
    });
}

// 显示导入模态框
function showImportModal() {
    document.getElementById('importFile').value = '';
    const modal = new bootstrap.Modal(document.getElementById('importModal'));
    modal.show();
}

// 导入TMX文件
async function importTMX() {
    const fileInput = document.getElementById('importFile');
    const file = fileInput.files[0];
    
    if (!file) {
        alert('请选择TMX文件');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await axios.post('/api/vector-db/import', formData);
        
        if (response.data.success || response.data.imported !== undefined) {
            showSuccess(`成功导入 ${response.data.imported} 条翻译记忆`);
            bootstrap.Modal.getInstance(document.getElementById('importModal')).hide();
            loadStatistics();
            loadTranslations();
        } else {
            showError('导入失败: ' + response.data.error);
        }
        
    } catch (error) {
        showError('导入失败: ' + error.message);
    }
}

// 导出TMX文件
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
        window.URL.revokeObjectURL(url);
        
    } catch (error) {
        showError('导出失败: ' + error.message);
    }
}

// 清空数据库
async function clearDatabase() {
    if (!confirm('确定要清空整个翻译记忆库吗？此操作不可恢复！')) {
        return;
    }
    
    if (!confirm('再次确认：这将删除所有翻译记忆数据！')) {
        return;
    }
    
    try {
        const response = await axios.delete('/api/vector-db/clear');
        
        if (response.data.success) {
            showSuccess('翻译记忆库已清空');
            loadStatistics();
            loadTranslations();
        } else {
            showError('清空失败: ' + response.data.error);
        }
        
    } catch (error) {
        showError('清空失败: ' + error.message);
    }
}

// 工具函数
function getLanguageName(code) {
    const names = {
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
    };
    return names[code] || code;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showLoading(show) {
    const indicator = document.getElementById('loadingIndicator');
    indicator.style.display = show ? 'block' : 'none';
}

function showSuccess(message) {
    // 可以使用更好的通知组件，这里简单使用alert
    alert(message);
}

function showError(message) {
    alert('错误: ' + message);
} 