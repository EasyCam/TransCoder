from flask import Flask, render_template, request, jsonify, send_file, Response
from flask_cors import CORS
import os
import json
import config
from services.translation_service import TranslationService
from services.vector_db_service import VectorDBService
from services.terminology_service import TerminologyService
from services.evaluation_service import EvaluationService
from utils.file_handler import FileHandler

app = Flask(__name__)
app.config.from_object(config)
CORS(app)

# 初始化服务
translation_service = TranslationService()
vector_db_service = VectorDBService()
terminology_service = TerminologyService()
evaluation_service = EvaluationService()
file_handler = FileHandler()

# 确保必要的目录存在
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(config.VECTOR_DB_PATH, exist_ok=True)
os.makedirs(config.TERMINOLOGY_DB_PATH, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/terminology')
def terminology_management():
    """术语库管理页面"""
    return render_template('terminology.html')

@app.route('/vector-db')
def vector_db_management():
    """翻译记忆库管理页面"""
    return render_template('vector_db.html')

@app.route('/api/translate', methods=['POST'])
def translate():
    """处理翻译请求"""
    try:
        data = request.json
        source_text = data.get('source_text', '')
        source_lang = data.get('source_lang', 'auto')
        target_langs = data.get('target_langs', [])
        use_vector_db = data.get('use_vector_db', True)
        use_terminology = data.get('use_terminology', True)
        model = data.get('model', None)  # 获取指定的模型
        
        if not source_text:
            return jsonify({'error': '请输入要翻译的文本'}), 400
        
        if not target_langs:
            return jsonify({'error': '请选择至少一种目标语言'}), 400
        
        # 执行翻译
        results = translation_service.translate(
            source_text=source_text,
            source_lang=source_lang,
            target_langs=target_langs,
            use_vector_db=use_vector_db,
            use_terminology=use_terminology,
            vector_db_service=vector_db_service,
            terminology_service=terminology_service,
            model=model
        )
        
        return jsonify(results)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/translate/stream', methods=['POST'])
def translate_stream():
    """处理流式翻译请求"""
    try:
        data = request.json
        source_text = data.get('source_text', '')
        source_lang = data.get('source_lang', 'auto')
        target_langs = data.get('target_langs', [])
        use_vector_db = data.get('use_vector_db', True)
        use_terminology = data.get('use_terminology', True)
        model = data.get('model', None)
        
        if not source_text:
            return jsonify({'error': '请输入要翻译的文本'}), 400
        
        if not target_langs:
            return jsonify({'error': '请选择至少一种目标语言'}), 400
        
        def generate():
            try:
                # 发送初始化信息
                init_data = {
                    'type': 'init',
                    'source_text': source_text,
                    'source_lang': source_lang,
                    'target_langs': target_langs,
                    'model': model or config.OLLAMA_MODEL
                }
                yield f"data: {json.dumps(init_data, ensure_ascii=False)}\n\n"
                
                # 执行流式翻译
                for chunk in translation_service.translate_streaming(
                    source_text=source_text,
                    source_lang=source_lang,
                    target_langs=target_langs,
                    use_vector_db=use_vector_db,
                    use_terminology=use_terminology,
                    vector_db_service=vector_db_service,
                    terminology_service=terminology_service,
                    model=model
                ):
                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                
                # 发送完成信号
                yield f"data: {json.dumps({'type': 'finished'}, ensure_ascii=False)}\n\n"
                
            except Exception as e:
                error_data = {
                    'type': 'error',
                    'error': str(e)
                }
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
        
        return Response(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Cache-Control'
            }
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/translate/reflect', methods=['POST'])
def reflect_translation():
    """对翻译进行反思"""
    try:
        data = request.json
        source_text = data.get('source_text', '')
        translation = data.get('translation', '')
        source_lang = data.get('source_lang', 'auto')
        target_lang = data.get('target_lang', '')
        model = data.get('model', None)
        
        if not source_text or not translation:
            return jsonify({'error': '请提供源文本和翻译'}), 400
        
        result = translation_service.reflect_translation(
            source_text=source_text,
            translation=translation,
            source_lang=source_lang,
            target_lang=target_lang,
            model=model
        )
        
        return jsonify({
            'reflection': result['reflection'],
            'metrics': result['metrics']
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/translate/improve', methods=['POST'])
def improve_translation():
    """根据反思改进翻译"""
    try:
        data = request.json
        source_text = data.get('source_text', '')
        current_translation = data.get('current_translation', '')
        reflection = data.get('reflection', '')
        source_lang = data.get('source_lang', 'auto')
        target_lang = data.get('target_lang', '')
        model = data.get('model', None)
        
        if not source_text or not current_translation or not reflection:
            return jsonify({'error': '请提供完整的信息'}), 400
        
        result = translation_service.improve_translation(
            source_text=source_text,
            current_translation=current_translation,
            reflection=reflection,
            source_lang=source_lang,
            target_lang=target_lang,
            model=model
        )
        
        return jsonify({
            'improved_translation': result['improved_translation'],
            'metrics': result['metrics']
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    """评价翻译质量"""
    try:
        data = request.json
        source_text = data.get('source_text', '')
        translated_text = data.get('translated_text', '')
        reference_text = data.get('reference_text', '')
        metrics = data.get('metrics', ['bleu'])
        
        scores = evaluation_service.evaluate(
            source_text=source_text,
            translated_text=translated_text,
            reference_text=reference_text,
            metrics=metrics
        )
        
        return jsonify(scores)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/terminology/upload', methods=['POST'])
def upload_terminology():
    """上传术语库"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '没有文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
        
        # 保存并处理文件
        filepath = file_handler.save_uploaded_file(file)
        result = terminology_service.import_terminology(filepath)
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/terminology/add', methods=['POST'])
def add_terminology():
    """添加单个术语"""
    try:
        data = request.json
        term = data.get('term', '')
        translations = data.get('translations', {})
        
        if not term:
            return jsonify({'error': '请输入术语'}), 400
        
        if not translations:
            return jsonify({'error': '请提供至少一个翻译'}), 400
        
        result = terminology_service.add_term(term, translations)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/terminology/export', methods=['GET'])
def export_terminology():
    """导出术语库"""
    try:
        format_type = request.args.get('format', 'csv')
        filepath = terminology_service.export_terminology(format_type)
        
        return send_file(filepath, as_attachment=True)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/terminology/list', methods=['GET'])
def list_terminology():
    """获取术语库列表"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        search = request.args.get('search', '')
        
        result = terminology_service.list_terms(page, per_page, search)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/terminology/delete', methods=['DELETE'])
def delete_terminology():
    """删除术语"""
    try:
        data = request.json
        term = data.get('term', '')
        
        if not term:
            return jsonify({'error': '请提供术语名称'}), 400
        
        result = terminology_service.delete_term(term)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/terminology/update', methods=['PUT'])
def update_terminology():
    """更新术语"""
    try:
        data = request.json
        term = data.get('term', '')
        translations = data.get('translations', {})
        
        if not term:
            return jsonify({'error': '请提供术语名称'}), 400
        
        result = terminology_service.update_term(term, translations)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/terminology/stats', methods=['GET'])
def get_terminology_stats():
    """获取术语库统计信息"""
    try:
        stats = terminology_service.get_statistics()
        return jsonify(stats)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/vector-db/add', methods=['POST'])
def add_to_vector_db():
    """添加翻译对到向量数据库"""
    try:
        data = request.json
        source_text = data.get('source_text', '')
        translations = data.get('translations', {})
        
        result = vector_db_service.add_translation_pair(source_text, translations)
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/vector-db/export', methods=['GET'])
def export_vector_db():
    """导出翻译记忆库"""
    try:
        format_type = request.args.get('format', 'tmx')
        filepath = vector_db_service.export_translation_memory(format_type)
        
        return send_file(filepath, as_attachment=True)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/vector-db/list', methods=['GET'])
def list_vector_db():
    """获取翻译记忆库列表"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        search = request.args.get('search', '')
        
        result = vector_db_service.list_translations(page, per_page, search)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/vector-db/delete', methods=['DELETE'])
def delete_vector_db_item():
    """删除翻译记忆库条目"""
    try:
        data = request.json
        index = data.get('index', -1)
        
        if index < 0:
            return jsonify({'error': '请提供有效的索引'}), 400
        
        result = vector_db_service.delete_translation(index)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/vector-db/search', methods=['POST'])
def search_vector_db():
    """搜索相似翻译"""
    try:
        data = request.json
        query = data.get('query', '')
        k = data.get('k', 10)
        
        if not query:
            return jsonify({'error': '请提供搜索查询'}), 400
        
        result = vector_db_service.search_similar_translations(query, k)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/vector-db/import', methods=['POST'])
def import_vector_db():
    """导入翻译记忆库"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '没有文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
        
        filepath = file_handler.save_uploaded_file(file)
        result = vector_db_service.import_translation_memory(filepath, 'tmx')
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/vector-db/stats', methods=['GET'])
def get_vector_db_stats():
    """获取翻译记忆库统计信息"""
    try:
        stats = vector_db_service.get_statistics()
        return jsonify(stats)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/vector-db/clear', methods=['DELETE'])
def clear_vector_db():
    """清空翻译记忆库"""
    try:
        result = vector_db_service.clear_all()
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/languages', methods=['GET'])
def get_languages():
    """获取支持的语言列表"""
    return jsonify(config.SUPPORTED_LANGUAGES)

@app.route('/api/models', methods=['GET'])
def get_models():
    """获取可用的Ollama模型列表"""
    try:
        models = translation_service.get_available_models()
        # 返回模型列表和默认模型
        return jsonify({
            'models': models,
            'default': config.OLLAMA_MODEL
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=config.DEBUG, host='0.0.0.0', port=6000) 