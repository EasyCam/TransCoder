"""
TransCoder Flask Web Application

Provides web interface and REST API for the translation platform.
"""

import json
import os
import time
from typing import Optional

from flask import Flask, Response, jsonify, render_template, request
from flask_cors import CORS

from transcoder.api import TransCoderAPI

CONFIG_FILE = "data/config.json"


def _list_team_endpoints() -> list:
    """Safe (key-free) listing of locally configured endpoints for the UI.

    Read-only; never probes the network; never serializes api keys
    (to_safe_dict masks them). Appends the ``edge-local`` pseudo-endpoint
    (local transformers runtime, weights from RESULTS/edge_download_log.json).
    """
    from transcoder.endpoints import EDGE_LOCAL_NAME, discover_endpoints, edge_models

    eps = []
    for ep in sorted(discover_endpoints().values(), key=lambda e: e.name):
        safe = ep.to_safe_dict()
        safe["editable"] = ep.source == "user json"
        eps.append(safe)
    local = edge_models()
    if local:
        eps.insert(0, {
            "name": EDGE_LOCAL_NAME,
            "base_url": "local://transformers",
            "api": "local",
            "models": local,
            "source": "local-transformers",
            "has_api_key": False,
            "masked_key": None,
        })
    return eps


def load_config() -> dict:
    """Load configuration from file."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"use_proxy": False, "proxy_url": ""}


def save_config(config: dict) -> None:
    """Save configuration to file."""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def create_app(config: Optional[dict] = None) -> Flask:
    """Create and configure Flask application."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    template_dir = os.path.join(base_dir, "templates")
    static_dir = os.path.join(base_dir, "static")
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    try:
        app.config["ASSET_V"] = int(os.path.getmtime(os.path.join(static_dir, "js", "app.js")))
    except OSError:
        app.config["ASSET_V"] = 0
    app.jinja_env.globals["asset_v"] = app.config["ASSET_V"]

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    CORS(app)

    # Fill the real-exam library on startup (throttled, non-blocking).
    try:
        from transcoder.real_sync import start_background_sync

        start_background_sync()
    except Exception:
        pass

    app_config = load_config()
    provider_type = os.getenv("LLM_PROVIDER", "ollama")
    model = os.getenv("OLLAMA_MODEL", "qwen3:0.6b" if provider_type == "ollama" else "gpt-4o-mini")
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    api = TransCoderAPI(
        model=model,
        ollama_host=ollama_host,
        provider_type=provider_type,
        use_proxy=app_config.get("use_proxy", False),
        proxy_url=app_config.get("proxy_url"),
    )

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
        from transcoder.samples import random_sample

        return render_template("index.html", sample=random_sample())

    @app.route("/terminology")
    def terminology_page():
        return render_template("terminology.html")

    @app.route("/vector-db")
    def vector_db_page():
        return render_template("vector_db.html")

    # API Routes
    @app.route("/api/models", methods=["GET"])
    def get_models():
        """Model list. With ?endpoint=<name> the list comes from THAT configured
        endpoint (live GET /models, falling back to the configured model list);
        without the parameter the legacy default provider is used."""
        ep_name = request.args.get("endpoint")
        if not ep_name:
            result = api.get_available_models()
            return jsonify(result.to_dict())

        from transcoder.endpoints import redact
        from transcoder.team_setup import endpoint_model_list, provider_for_endpoint

        err = None
        models: list = []
        live = False
        try:
            provider = provider_for_endpoint(ep_name)
            try:
                try:
                    models = list(provider.get_available_models(raise_on_error=True) or [])
                except TypeError:
                    models = list(provider.get_available_models() or [])
                live = bool(models)
            except Exception as exc:  # unreachable endpoint / not implemented
                err = str(redact(str(exc)))
        except Exception as exc:
            err = str(redact(str(exc)))
        if not models:
            models = endpoint_model_list(ep_name)
        return jsonify({
            "success": True,
            "models": models,
            "default": models[0] if models else None,
            "endpoint": ep_name,
            "live": live,
            "note": None if live else (err or "端点不可达，显示配置列表"),
        })

    @app.route("/api/endpoints", methods=["GET"])
    def endpoints_list():
        """Configured endpoints for the UI (keys never leave the server)."""
        return jsonify({"endpoints": _list_team_endpoints()})

    @app.route("/api/endpoints/import", methods=["POST"])
    def endpoints_import():
        """Copy a discovered endpoint (key included) into the user library."""
        from transcoder.endpoints import import_endpoint

        data = request.json or {}
        try:
            ep = import_endpoint(data.get("name", ""))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"success": True, "name": ep.name})

    @app.route("/api/endpoints/manual", methods=["POST"])
    def endpoints_manual():
        """Add or update a manually entered endpoint (base URL, key, models)."""
        from transcoder.endpoints import upsert_user_endpoint

        data = request.json or {}
        models = data.get("models") or []
        if isinstance(models, str):
            models = [m.strip() for m in models.split(",") if m.strip()]
        try:
            upsert_user_endpoint(
                name=data.get("name", ""),
                base_url=data.get("base_url", ""),
                api_key=(data.get("api_key") or None),
                models=models,
                api=data.get("api") or "openai-completions",
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"success": True})

    @app.route("/api/endpoints/manual/<name>", methods=["DELETE"])
    def endpoints_manual_delete(name):
        from transcoder.endpoints import delete_user_endpoint

        ok = delete_user_endpoint(name)
        return (jsonify({"success": True}) if ok else (jsonify({"error": "not found"}), 404))

    @app.route("/api/languages", methods=["GET"])
    def get_languages():
        return jsonify(api.get_supported_languages())

    # ---- TransCoder-NEXT team mode (P3) --------------------------------- #
    @app.route("/api/team/endpoints", methods=["GET"])
    def team_endpoints():
        """Locally configured endpoints (safe dicts, keys masked, no probing)."""
        return jsonify({"endpoints": _list_team_endpoints()})

    @app.route("/api/translate/team", methods=["POST"])
    def translate_team():
        """Multi-agent team translation for ONE direction."""
        from transcoder.orchestrator import EventLog
        from transcoder.team_setup import build_team_from_endpoints

        data = request.json or {}
        source_text = data.get("source_text", "")
        source_lang = data.get("source_lang", "auto")
        target_lang = data.get("target_lang", "")
        translator_endpoint = data.get("translator_endpoint")
        translator_model = data.get("translator_model")
        reviewer_endpoint = data.get("reviewer_endpoint")
        reviewer_model = data.get("reviewer_model")
        reviewer_fallback_endpoint = data.get("reviewer_fallback_endpoint")
        reviewer_fallback_model = data.get("reviewer_fallback_model")
        review_strategy = (data.get("review_strategy") or "auto").lower()
        team_rounds = max(1, int(data.get("team_rounds", 3)))
        dry = bool(data.get("dry", False))
        use_terminology = data.get("use_terminology", False)
        use_vector_db = data.get("use_vector_db", False)
        seed = data.get("seed")

        if not source_text:
            return jsonify({"error": "请输入要翻译的文本"}), 400
        if not target_lang:
            return jsonify({"error": "请选择目标语言"}), 400
        if not translator_endpoint:
            return jsonify({"error": "team 模式需要 translator_endpoint（见 /api/team/endpoints）"}), 400

        terminology = api.terminology if use_terminology else None
        vector_db = api.vector_db if use_vector_db else None

        # Review strategy: cloud-first, local fallback/assist.
        if review_strategy == "none":
            reviewer_endpoint = reviewer_fallback_endpoint = None
            reviewer_model = reviewer_fallback_model = None
        elif review_strategy == "local":
            reviewer_endpoint = reviewer_fallback_endpoint or "edge-local"
            reviewer_model = reviewer_fallback_model or None
            reviewer_fallback_endpoint = None
            reviewer_fallback_model = None
        elif review_strategy == "auto" and not reviewer_fallback_endpoint:
            # primary reviewer (usually online) falls back to the local reviewer
            try:
                from transcoder.endpoints import EDGE_LOCAL_NAME, edge_models

                local_models = edge_models()
                if reviewer_endpoint != EDGE_LOCAL_NAME and local_models:
                    reviewer_fallback_endpoint = EDGE_LOCAL_NAME
                    reviewer_fallback_model = "gemma3:270m" if "gemma3:270m" in local_models else local_models[0]
            except Exception:
                pass

        try:
            orchestrator = build_team_from_endpoints(
                translator_endpoint=translator_endpoint,
                translator_model=translator_model,
                reviewer_endpoint=reviewer_endpoint,
                reviewer_model=reviewer_model,
                reviewer_fallback_endpoint=reviewer_fallback_endpoint,
                reviewer_fallback_model=reviewer_fallback_model,
                terminology_service=terminology,
                vector_db_service=vector_db,
                local_fallback=api.translation_service,
                max_rounds=team_rounds,
                event_log=EventLog(),
                seed=seed,
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        team_result = orchestrator.run(source_text, source_lang, target_lang, dry=dry)
        return jsonify({
            "success": True,
            "target_lang": target_lang,
            "team": team_result.to_dict(),
        })

    @app.route("/api/translate", methods=["POST"])
    def translate():
        data = request.json
        source_text = data.get("source_text", "")
        source_lang = data.get("source_lang", "auto")
        target_langs = data.get("target_langs", [])
        model = data.get("model")
        use_vector_db = data.get("use_vector_db", False)
        use_terminology = data.get("use_terminology", False)
        endpoint = data.get("endpoint") or None

        if not source_text:
            return jsonify({"error": "请输入要翻译的文本"}), 400
        if not target_langs:
            return jsonify({"error": "请选择至少一种目标语言"}), 400

        try:
            result = api.translate(
                source_text=source_text,
                source_lang=source_lang,
                target_langs=target_langs,
                model=model,
                use_vector_db=use_vector_db,
                use_terminology=use_terminology,
                endpoint=endpoint,
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
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
            endpoint=data.get("endpoint") or None,
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
            endpoint=data.get("endpoint") or None,
        )
        return jsonify(result.to_dict())

    @app.route("/api/translate/stream", methods=["POST"])
    def translate_stream():
        """Server-sent events with true token streaming per target language."""
        data = request.json or {}
        source_text = data.get("source_text", "")
        source_lang = data.get("source_lang", "auto")
        target_langs = data.get("target_langs", [])
        model = data.get("model")
        endpoint = data.get("endpoint") or None
        use_vector_db = bool(data.get("use_vector_db"))

        def sse(payload: dict) -> str:
            return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        def generate():
            yield sse({
                "type": "init",
                "source_text": source_text,
                "source_lang": source_lang,
                "target_langs": target_langs,
                "model": model or api.model,
            })
            try:
                service = api._service_for_endpoint(endpoint, model) if endpoint else api.translation_service
            except ValueError as exc:
                yield sse({"type": "error", "error": str(exc)})
                return

            for target_lang in target_langs:
                yield sse({"type": "start", "target_lang": target_lang, "start_time": time.time()})
                acc = []
                try:
                    for delta in service.translate_stream(
                        source_text, source_lang, target_lang, model=model,
                        vector_db_service=api.vector_db if use_vector_db else None,
                    ):
                        acc.append(delta)
                        yield sse({"type": "content", "target_lang": target_lang, "content": delta})
                except Exception as exc:
                    yield sse({"type": "error", "target_lang": target_lang, "error": str(exc)})
                    continue

                final = service._clean_translation("".join(acc))
                if use_vector_db and final.strip():
                    api.vector_db.add_translation_pair(source_text, {target_lang: final})
                yield sse({"type": "complete", "target_lang": target_lang, "final_content": final})

            yield sse({"type": "finished"})

        return Response(
            generate(), mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
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

    # ---- Teaching: human translation workbench + analytics --------------- #
    def _review_provider(data: dict):
        """Provider for grading/polishing: the chosen endpoint, or the default service provider."""
        from transcoder.team_setup import provider_for_endpoint

        endpoint = data.get("endpoint") or None
        model = data.get("model") or None
        if endpoint:
            provider = provider_for_endpoint(endpoint, model)
        else:
            provider = api.translation_service.provider
        model = model or getattr(provider, "default_model", None) or api.model
        return provider, model

    @app.route("/api/human/grade", methods=["POST"])
    def human_grade():
        """Score a human translation on the 4-dimension rubric; persist the submission."""
        from transcoder import teaching_store
        from transcoder.human_workbench import grade

        data = request.json or {}
        source_text = data.get("source_text", "")
        translation = data.get("translation", "")
        if not source_text or not translation:
            return jsonify({"error": "source_text and translation are required"}), 400
        try:
            provider, model = _review_provider(data)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        result = grade(
            provider, model, source_text, translation,
            source_lang=data.get("source_lang", "auto"),
            target_lang=data.get("target_lang", ""),
            temperature=float(data.get("temperature", 0.3)),
        )
        submission = None
        if data.get("save", True):
            submission = teaching_store.add_submission(
                source_text=source_text,
                translation=translation,
                source_lang=data.get("source_lang", ""),
                target_lang=data.get("target_lang", ""),
                grade=result,
                endpoint=data.get("endpoint"),
                model=model,
                author=data.get("author"),
            )
            teaching_store.record_event("human.grade", {
                "overall": result.get("overall"),
                "issues": len(result.get("issues") or []),
                "endpoint": data.get("endpoint"),
                "model": model,
            })
        return jsonify({
            "success": not result.get("error"),
            "grade": result,
            "submission_id": (submission or {}).get("id"),
        })

    @app.route("/api/human/polish", methods=["POST"])
    def human_polish():
        """Correct and polish a human translation; returns edits + polished text."""
        from transcoder import teaching_store
        from transcoder.human_workbench import polish

        data = request.json or {}
        source_text = data.get("source_text", "")
        translation = data.get("translation", "")
        if not source_text or not translation:
            return jsonify({"error": "source_text and translation are required"}), 400
        try:
            provider, model = _review_provider(data)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        result = polish(
            provider, model, source_text, translation,
            source_lang=data.get("source_lang", "auto"),
            target_lang=data.get("target_lang", ""),
            issues=data.get("issues"),
            temperature=float(data.get("temperature", 0.3)),
        )
        teaching_store.record_event("human.polish", {
            "edits": len(result.get("edits") or []),
            "parse_ok": result.get("parse_ok"),
            "endpoint": data.get("endpoint"),
            "model": model,
        })
        return jsonify({"success": not result.get("error"), "polish": result})

    @app.route("/api/human/submissions", methods=["GET", "POST"])
    def human_submissions():
        from transcoder import teaching_store

        if request.method == "POST":
            data = request.json or {}
            record = teaching_store.add_submission(
                source_text=data.get("source_text", ""),
                translation=data.get("translation", ""),
                source_lang=data.get("source_lang", ""),
                target_lang=data.get("target_lang", ""),
                grade=data.get("grade"),
                polish=data.get("polish"),
                endpoint=data.get("endpoint"),
                model=data.get("model"),
                author=data.get("author"),
            )
            teaching_store.record_event("human.submit", {"author": data.get("author")})
            return jsonify({"success": True, "submission": record})
        return jsonify({"success": True, "submissions": teaching_store.list_submissions(limit=100)})

    @app.route("/api/human/align", methods=["POST"])
    def human_align():
        """Fully automatic token correspondence (embeddings + Hungarian matching)."""
        from transcoder import teaching_store
        from transcoder.aligner import align_texts

        data = request.json or {}
        source_text = data.get("source_text", "")
        translation = data.get("translation", "")
        if not source_text or not translation:
            return jsonify({"error": "source_text and translation are required"}), 400
        try:
            result = align_texts(source_text, translation)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        teaching_store.record_event("human.auto_align", {
            "pairs": result.get("count"),
            "target_lang": data.get("target_lang"),
        })
        return jsonify({"success": True, "alignment": result})

    @app.route("/api/human/quick-score", methods=["POST"])
    def human_quick_score():
        """Fast local semantic score (embeddings, optional reference + chrF)."""
        from transcoder import teaching_store
        from transcoder.semantic_scorer import get_scorer

        data = request.json or {}
        source_text = data.get("source_text", "")
        translation = data.get("translation", "")
        if not source_text or not translation:
            return jsonify({"error": "source_text and translation are required"}), 400
        try:
            result = get_scorer().score(source_text, translation, data.get("reference"))
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        teaching_store.record_event("human.quick_score", {
            "semantic_score": result.get("semantic_score"),
            "combined_score": result.get("combined_score"),
            "target_lang": data.get("target_lang"),
        })
        return jsonify({"success": True, "score": result})

    @app.route("/api/human/annotations", methods=["GET", "POST"])
    def human_annotations():
        from transcoder import teaching_store

        if request.method == "POST":
            data = request.json or {}
            if not data.get("submission_id"):
                return jsonify({"error": "submission_id is required"}), 400
            record = teaching_store.add_annotation(
                submission_id=data["submission_id"],
                quote=data.get("quote", ""),
                note=data.get("note", ""),
                kind=data.get("kind", "note"),
                start=data.get("start"),
                end=data.get("end"),
                target_lang=data.get("target_lang"),
                author=data.get("author"),
                src_quote=data.get("src_quote"),
                src_start=data.get("src_start"),
                src_end=data.get("src_end"),
            )
            teaching_store.record_event("annotation.add", {"kind": record.get("kind")})
            return jsonify({"success": True, "annotation": record})
        return jsonify({
            "success": True,
            "annotations": teaching_store.list_annotations(
                submission_id=request.args.get("submission_id"),
                limit=int(request.args.get("limit", 200)),
            ),
        })

    @app.route("/api/human/annotations/<annotation_id>", methods=["DELETE"])
    def human_annotation_delete(annotation_id):
        from transcoder import teaching_store

        ok = teaching_store.delete_annotation(annotation_id)
        return (jsonify({"success": True}) if ok else (jsonify({"error": "not found"}), 404))

    # ---- Writing workspace (TCFL essay grading) -------------------------- #
    @app.route("/api/writing/prompt", methods=["GET"])
    def writing_prompt():
        from transcoder.writing_prompts import random_prompt

        lang = request.args.get("lang", "zh")
        return jsonify({"success": True, "prompt": random_prompt(lang), "language": lang})

    @app.route("/api/writing/grade", methods=["POST"])
    def writing_grade():
        """Rubric grading for an essay (content/organization/grammar/vocabulary/coherence)."""
        from transcoder import teaching_store
        from transcoder.writing import grade_writing

        data = request.json or {}
        prompt = data.get("prompt", "")
        essay = data.get("essay", "")
        if not prompt or not essay.strip():
            return jsonify({"error": "prompt and essay are required"}), 400
        try:
            provider, model = _review_provider(data)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        lang = data.get("lang", "zh")
        result = grade_writing(
            provider, model, prompt, essay,
            temperature=float(data.get("temperature", 0.3)),
            length_hint=data.get("length_hint"),
            language=lang,
        )
        submission = None
        if data.get("save", True) and result.get("parse_ok"):
            submission = teaching_store.add_submission(
                source_text=prompt,
                translation=essay,
                source_lang="prompt",
                target_lang={"zh": "zh-cn"}.get(lang, lang),
                grade=result,
                endpoint=data.get("endpoint"),
                model=model,
                author=data.get("author"),
            )
            teaching_store.record_event("writing.grade", {
                "overall": result.get("overall"),
                "issues": len(result.get("issues") or []),
                "level": result.get("level"),
                "author": data.get("author"),
            })
        return jsonify({
            "success": bool(result.get("parse_ok")),
            "grade": result,
            "submission_id": (submission or {}).get("id"),
        })

    @app.route("/api/writing/polish", methods=["POST"])
    def writing_polish():
        """Correct and improve an essay, returning the revised text and edit list."""
        from transcoder import teaching_store
        from transcoder.writing import polish_writing

        data = request.json or {}
        prompt = data.get("prompt", "")
        essay = data.get("essay", "")
        if not prompt or not essay.strip():
            return jsonify({"error": "prompt and essay are required"}), 400
        try:
            provider, model = _review_provider(data)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        result = polish_writing(
            provider, model, prompt, essay,
            temperature=float(data.get("temperature", 0.3)),
            language=data.get("lang", "zh"),
        )
        teaching_store.record_event("writing.polish", {
            "edits": len(result.get("edits") or []),
            "parse_ok": result.get("parse_ok"),
            "author": data.get("author"),
        })
        return jsonify({"success": bool(result.get("parse_ok")), "polish": result})

    # ---- Content library import / export --------------------------------- #
    @app.route("/api/content/export/<kind>", methods=["GET"])
    def content_export(kind):
        """Download a JSON snapshot of one content bank."""
        from flask import Response

        from transcoder.content_store import export_content

        try:
            payload = export_content(kind)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        body = json.dumps(payload, ensure_ascii=False, indent=2)
        return Response(body, mimetype="application/json", headers={
            "Content-Disposition": f'attachment; filename="transcoder-{kind}.json"',
        })

    @app.route("/api/content/import/<kind>", methods=["POST"])
    def content_import(kind):
        """Import a JSON snapshot (request body or uploaded file)."""
        from transcoder import teaching_store
        from transcoder.content_store import import_content

        payload = None
        if request.files.get("file") is not None:
            try:
                payload = json.loads(request.files["file"].read().decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as e:
                return jsonify({"error": f"invalid JSON: {e}"}), 400
        else:
            payload = request.get_json(silent=True)
        if payload is None:
            return jsonify({"error": "JSON body or file is required"}), 400
        try:
            result = import_content(kind, payload)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        teaching_store.record_event("content.import", {"kind": kind, **result})
        return jsonify({"success": True, **result})

    # ---- Reading comprehension (CET-4/6, postgraduate) ------------------- #
    @app.route("/api/reading/catalog", methods=["GET"])
    def reading_catalog():
        """Selectable papers: exam / year / paper / title (no answers)."""
        from transcoder.reading_bank import catalog

        return jsonify({"success": True, "items": catalog()})

    @app.route("/api/reading/article", methods=["GET"])
    def reading_article():
        from transcoder.reading_bank import get_article, public_article

        article = get_article(request.args.get("id", ""))
        if article is None:
            return jsonify({"error": "not found"}), 404
        return jsonify({"success": True, "article": public_article(article)})

    @app.route("/api/reading/random", methods=["GET"])
    def reading_random():
        from transcoder.reading_bank import random_article

        return jsonify({"success": True, "article": random_article(
            request.args.get("exam") or None,
            request.args.get("year") or None,
            request.args.get("paper") or None,
        )})

    @app.route("/api/reading/import", methods=["POST"])
    def reading_import():
        """Import a real paper (or any article) into the local library."""
        from transcoder import teaching_store
        from transcoder.reading_store import add_user_article

        try:
            article = add_user_article(request.json or {})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        teaching_store.record_event("reading.import", {"exam": article.get("exam"), "year": article.get("year")})
        return jsonify({"success": True, "article": {k: article[k] for k in ("id", "exam", "year", "paper", "title")}})

    @app.route("/api/reading/import/<article_id>", methods=["DELETE"])
    def reading_import_delete(article_id):
        from transcoder.reading_store import delete_user_article

        ok = delete_user_article(article_id)
        return (jsonify({"success": True}) if ok else (jsonify({"error": "not found"}), 404))

    @app.route("/api/reading/check", methods=["POST"])
    def reading_check():
        from transcoder import teaching_store
        from transcoder.reading_bank import check_answers

        data = request.json or {}
        try:
            result = check_answers(data.get("id", ""), list(data.get("answers") or []))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        teaching_store.record_event("reading.check", {
            "exam": result.get("exam"), "score": result.get("score"), "total": result.get("total"),
        })
        return jsonify({"success": True, "result": result})

    @app.route("/api/reading/github/options", methods=["GET"])
    def reading_github_options():
        """Available real-paper years/sessions (requires GitHub access)."""
        from transcoder.real_exams import list_options

        try:
            return jsonify({"success": True, "options": list_options()})
        except Exception as e:
            return jsonify({"error": str(e)}), 502

    @app.route("/api/reading/fetch_github", methods=["POST"])
    def reading_fetch_github():
        """Download real papers from GitHub and add them to the local library."""
        from transcoder import teaching_store
        from transcoder.reading_store import add_user_article
        from transcoder.real_exams import fetch_cet, fetch_kaoyan

        data = request.json or {}
        source = data.get("source", "kaoyan1")
        year = (data.get("year") or "").strip()
        try:
            if source in ("kaoyan1", "kaoyan2"):
                paper = "english-i" if source == "kaoyan1" else "english-ii"
                articles = fetch_kaoyan(paper, [year] if year and year != "all" else None)
            elif source in ("cet4", "cet6"):
                articles = fetch_cet(source.upper(), None if not year or year == "all" else year)
            else:
                return jsonify({"error": f"unknown source: {source}"}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 502

        imported = []
        for a in articles:
            try:
                stored = add_user_article(a)
                imported.append({
                    "id": stored["id"], "exam": stored["exam"], "year": stored["year"],
                    "paper": stored["paper"], "title": stored["title"],
                    "has_key": stored.get("has_key", True),
                })
            except ValueError:
                continue
        teaching_store.record_event("reading.fetch_github", {
            "source": source, "year": year, "imported": len(imported),
        })
        return jsonify({"success": True, "imported": len(imported), "articles": imported})

    # ---- Read-aloud / shadowing ------------------------------------------ #
    @app.route("/api/speech/passage", methods=["GET"])
    def speech_passage():
        import random

        from transcoder.speech import PASSAGES_BY_LANG

        lang = request.args.get("lang", "zh")
        bank = list(PASSAGES_BY_LANG.get(lang) or PASSAGES_BY_LANG["zh"])
        try:
            from transcoder.content_store import user_speech_passages

            bank += [p for p in user_speech_passages() if (p.get("lang") or "zh") == lang]
        except Exception:
            pass
        return jsonify({"success": True, "passage": dict(random.choice(bank)), "language": lang})

    @app.route("/api/speech/annotate", methods=["POST"])
    def speech_annotate():
        """Reading aids: pinyin / IPA / romaji + kana."""
        from transcoder.speech import annotate

        data = request.json or {}
        text = data.get("text", "")
        if not text:
            return jsonify({"error": "text is required"}), 400
        try:
            return jsonify({"success": True, "annotation": annotate(text, data.get("lang", "zh"))})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/speech/diagnose", methods=["POST"])
    def speech_diagnose():
        """Explain pronunciation problems with the review model."""
        from transcoder import teaching_store
        from transcoder.speech import diagnose_pronunciation

        data = request.json or {}
        target = data.get("target_text", "")
        transcript = data.get("transcript", "")
        if not target or not transcript:
            return jsonify({"error": "target_text and transcript are required"}), 400
        try:
            provider, model = _review_provider(data)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        result = diagnose_pronunciation(
            provider, model, target, transcript,
            language=data.get("language", "zh"), items=data.get("items") or [],
        )
        teaching_store.record_event("speech.diagnose", {
            "issues": len(result.get("issues") or []),
            "language": data.get("language"),
        })
        return jsonify({"success": bool(result.get("parse_ok")), "diagnosis": result})

    @app.route("/api/speech/tts", methods=["POST"])
    def speech_tts():
        """Synthesize the passage with a local Chinese voice (cached m4a)."""
        from transcoder import teaching_store
        from transcoder.speech import synthesize

        data = request.json or {}
        text = data.get("text", "")
        try:
            info = synthesize(text, lang=data.get("lang", "zh"), voice=data.get("voice"))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        teaching_store.record_event("speech.tts", {"chars": len(text), "voice": info.get("voice")})
        return jsonify({"success": True, "audio": info, "url": "/api/speech/audio/" + info["file"]})

    @app.route("/api/speech/audio/<name>", methods=["GET"])
    def speech_audio(name):
        import re

        from flask import send_from_directory

        from transcoder.speech import AUDIO_DIR

        if not re.fullmatch(r"tts_[0-9a-f]{20}\.m4a", name):
            return jsonify({"error": "not found"}), 404
        return send_from_directory(str(AUDIO_DIR), name, mimetype="audio/mp4")

    @app.route("/api/speech/score", methods=["POST"])
    def speech_score():
        """Transcribe a learner recording and score it character by character."""
        import os
        import tempfile

        from transcoder import teaching_store
        from transcoder.speech import score_reading, transcribe

        target = (request.form.get("target_text") or "").strip()
        upload = request.files.get("file")
        if not target or upload is None:
            return jsonify({"error": "target_text and file are required"}), 400
        suffix = os.path.splitext(upload.filename or "rec.webm")[1] or ".webm"
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        try:
            upload.save(path)
            lang = request.form.get("language", "zh")
            asr = transcribe(path, language=lang)
            result = score_reading(target, asr["text"], lang)
            result["duration"] = asr.get("duration")
            result["language"] = asr.get("language")
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        teaching_store.record_event("speech.score", {
            "score": result.get("score"),
            "accuracy": result.get("accuracy"),
            "missing": result.get("missing"),
        })
        return jsonify({"success": True, "result": result})

    @app.route("/api/telemetry", methods=["POST"])
    def telemetry_record():
        from transcoder import teaching_store

        data = request.json or {}
        event = data.get("event")
        if not event:
            return jsonify({"error": "event is required"}), 400
        teaching_store.record_event(event, data.get("payload"))
        return jsonify({"success": True})

    @app.route("/api/telemetry/summary", methods=["GET"])
    def telemetry_summary():
        from transcoder import teaching_store

        return jsonify({
            "success": True,
            "summary": teaching_store.telemetry_summary(days=int(request.args.get("days", 7))),
        })

    @app.route("/api/config", methods=["GET"])
    def get_config():
        config = load_config()
        return jsonify(config)

    @app.route("/api/config", methods=["POST"])
    def update_config():
        data = request.json
        config = load_config()
        config["use_proxy"] = data.get("use_proxy", False)
        config["proxy_url"] = data.get("proxy_url", "")
        save_config(config)
        return jsonify({"success": True, "message": "配置已保存，重启服务后生效"})

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
