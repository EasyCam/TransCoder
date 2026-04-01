"""
TransCoder Flask Web Application

Provides web interface and REST API for the translation platform.
"""

import json
import os
from typing import Optional

from flask import Flask, Response, jsonify, render_template, request
from flask_cors import CORS

from transcoder.api import TransCoderAPI


def create_app(config: Optional[dict] = None) -> Flask:
    """Create and configure Flask application."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    template_dir = os.path.join(base_dir, "templates")
    static_dir = os.path.join(base_dir, "static")
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

    # Configuration
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB

    CORS(app)

    # Initialize API
    provider_type = os.getenv("LLM_PROVIDER", "ollama")
    model = os.getenv("OLLAMA_MODEL", "qwen3:0.6b" if provider_type == "ollama" else "gpt-4o-mini")
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    api = TransCoderAPI(model=model, ollama_host=ollama_host, provider_type=provider_type)

    # Ensure directories exist
    os.makedirs("data/vector_db", exist_ok=True)
    os.makedirs("data/terminology", exist_ok=True)
    os.makedirs("uploads", exist_ok=True)

    # Template context
    @app.context_processor
    def inject_languages():
        return {"supported_languages": api.get_supported_languages()}

    # Routes
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/terminology")
    def terminology_page():
        return render_template("terminology.html")

    @app.route("/vector-db")
    def vector_db_page():
        return render_template("vector_db.html")

    # API Routes
    @app.route("/api/models", methods=["GET"])
    def get_models():
        result = api.get_available_models()
        return jsonify(result.to_dict())

    @app.route("/api/languages", methods=["GET"])
    def get_languages():
        return jsonify(api.get_supported_languages())

    @app.route("/api/translate", methods=["POST"])
    def translate():
        data = request.json
        source_text = data.get("source_text", "")
        source_lang = data.get("source_lang", "auto")
        target_langs = data.get("target_langs", [])
        model = data.get("model")
        use_vector_db = data.get("use_vector_db", False)
        use_terminology = data.get("use_terminology", False)

        if not source_text:
            return jsonify({"error": "请输入要翻译的文本"}), 400
        if not target_langs:
            return jsonify({"error": "请选择至少一种目标语言"}), 400

        result = api.translate(
            source_text=source_text,
            source_lang=source_lang,
            target_langs=target_langs,
            model=model,
            use_vector_db=use_vector_db,
            use_terminology=use_terminology,
        )
        return jsonify(result.to_dict())

    @app.route("/api/translate/reflect", methods=["POST"])
    def reflect_translation():
        data = request.json
        result = api.reflect_translation(
            source_text=data.get("source_text", ""),
            translation=data.get("translation", ""),
            source_lang=data.get("source_lang", "auto"),
            target_lang=data.get("target_lang", ""),
            model=data.get("model"),
        )
        return jsonify(result.to_dict())

    @app.route("/api/translate/improve", methods=["POST"])
    def improve_translation():
        data = request.json
        result = api.improve_translation(
            source_text=data.get("source_text", ""),
            current_translation=data.get("current_translation", ""),
            reflection=data.get("reflection", ""),
            source_lang=data.get("source_lang", "auto"),
            target_lang=data.get("target_lang", ""),
            model=data.get("model"),
        )
        return jsonify(result.to_dict())

    @app.route("/api/translate/stream", methods=["POST"])
    def translate_stream():
        data = request.json
        source_text = data.get("source_text", "")
        source_lang = data.get("source_lang", "auto")
        target_langs = data.get("target_langs", [])
        model = data.get("model")

        def generate():
            init_data = {
                "type": "init",
                "source_text": source_text,
                "source_lang": source_lang,
                "target_langs": target_langs,
                "model": model or api.model,
            }
            yield f"data: {json.dumps(init_data, ensure_ascii=False)}\n\n"

            for target_lang in target_langs:
                start_data = {"type": "start", "target_lang": target_lang}
                yield f"data: {json.dumps(start_data, ensure_ascii=False)}\n\n"

                result = api.translate(
                    source_text=source_text, source_lang=source_lang, target_langs=[target_lang], model=model
                )

                if result.success:
                    trans_data = result.data.get("translations", {}).get(target_lang, {})
                    complete_data = {
                        "type": "complete",
                        "target_lang": target_lang,
                        "final_content": trans_data.get("text", ""),
                    }
                    yield f"data: {json.dumps(complete_data, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type': 'finished'}, ensure_ascii=False)}\n\n"

        return Response(
            generate(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )

    @app.route("/api/evaluate", methods=["POST"])
    def evaluate():
        data = request.json
        result = api.evaluate_translation(
            source_text=data.get("source_text", ""),
            translated_text=data.get("translated_text", ""),
            reference_text=data.get("reference_text"),
            metrics=data.get("metrics"),
        )
        return jsonify(result.to_dict())

    @app.route("/api/terminology/list", methods=["GET"])
    def list_terminology():
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 50))
        search = request.args.get("search", "")
        result = api.terminology.list_terms(page=page, per_page=per_page, search=search)
        return jsonify(result.to_dict())

    @app.route("/api/terminology/add", methods=["POST"])
    def add_terminology():
        data = request.json
        result = api.add_terminology(term=data.get("term", ""), translations=data.get("translations", {}))
        return jsonify(result.to_dict())

    @app.route("/api/vector-db/search", methods=["POST"])
    def search_vector_db():
        data = request.json
        result = api.search_similar_translations(query_text=data.get("query", ""), k=data.get("k", 5))
        return jsonify(result.to_dict())

    @app.route("/api/vector-db/add", methods=["POST"])
    def add_to_vector_db():
        data = request.json
        result = api.add_translation_memory(
            source_text=data.get("source_text", ""), translations=data.get("translations", {})
        )
        return jsonify(result.to_dict())

    @app.route("/api/vector-db/stats", methods=["GET"])
    def vector_db_stats():
        result = api.vector_db.get_statistics()
        return jsonify(result.to_dict())

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({"error": "Internal server error"}), 500

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5555)
