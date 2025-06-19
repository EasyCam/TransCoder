from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import os
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
    app.run(debug=config.DEBUG, host='0.0.0.0', port=5000) 