"""
TransCoder CLI - Command Line Interface

Usage:
    transcoder              Launch GUI (default)
    transcoder gui          Launch GUI interface
    transcoder web          Launch Web server
    transcoder cli          CLI mode for batch translation
    python -m transcoder    Module invocation
"""

import argparse
import sys


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser with unified flags."""
    parser = argparse.ArgumentParser(
        prog="transcoder",
        description="TransCoder - Multilingual Parallel Translation Platform with Reflection-based Improvement",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    transcoder                    Launch GUI (default)
    transcoder web --port 8080    Launch web server on port 8080
    transcoder cli -i input.txt -o output.txt -t en,ja,ko
    python -m transcoder web      Module invocation
        """,
    )

    # Unified flags
    parser.add_argument(
        "-V", "--version", action="version", version=f"transcoder {__import__('transcoder').__version__}"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON format")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress non-error output")

    # Mode selection
    subparsers = parser.add_subparsers(dest="mode", help="Operation mode")

    # GUI mode
    gui_parser = subparsers.add_parser("gui", help="Launch GUI interface")
    gui_parser.add_argument("--no-web", action="store_true", help="Disable embedded web server")

    # Web mode
    web_parser = subparsers.add_parser("web", help="Launch web server")
    web_parser.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    web_parser.add_argument("--port", type=int, default=5555, help="Port number (default: 5555)")
    web_parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    web_parser.add_argument("--production", action="store_true", help="Use production server (waitress)")

    # CLI mode
    cli_parser = subparsers.add_parser("cli", help="CLI mode for batch translation")
    cli_parser.add_argument("-i", "--input", required=True, help="Input file path")
    cli_parser.add_argument("-s", "--source-lang", default="auto", help="Source language (default: auto-detect)")
    cli_parser.add_argument(
        "-t", "--target-langs", required=True, help="Target languages (comma-separated, e.g., en,ja,ko)"
    )
    cli_parser.add_argument("-m", "--model", help="Model to use (default depends on provider)")
    cli_parser.add_argument(
        "--provider", choices=["ollama", "openai"], default="ollama", help="LLM provider (default: ollama)"
    )
    cli_parser.add_argument(
        "--mode-type",
        choices=["simple", "stream", "reflect", "triple", "iterate"],
        default="simple",
        help="Translation mode",
    )
    cli_parser.add_argument("--iterations", type=int, default=3, help="Iterations for iterate mode")
    cli_parser.add_argument("--use-vector-db", action="store_true", help="Use translation memory")
    cli_parser.add_argument("--use-terminology", action="store_true", help="Use terminology database")

    # Team mode (TransCoder-NEXT, spec-agent-design.md §5): --mode direct|reflection|iterative|team
    cli_parser.add_argument(
        "--mode",
        dest="run_mode",
        choices=["direct", "reflection", "iterative", "team"],
        default=None,
        help="Unified run-mode: direct baseline, reflection/iterative (existing single-"
        "model loops), team (multi-agent with reviewer). Overrides --mode-type when set.",
    )
    cli_parser.add_argument(
        "--translator-endpoint",
        help="team: configured endpoint name for the (edge) translator, e.g. ollama-local",
    )
    cli_parser.add_argument("--translator-model", help="team: translator model id (default: endpoint's first)")
    cli_parser.add_argument(
        "--reviewer-endpoint",
        help="team: configured endpoint name for the reviewer (omit => pure edge, degraded)",
    )
    cli_parser.add_argument("--reviewer-model", help="team: reviewer model id (default: endpoint's first)")
    cli_parser.add_argument("--team-rounds", type=int, default=3, help="team: max review rounds (default: 3)")
    cli_parser.add_argument("--seed", type=int, default=None, help="Sampling seed (team/experiments)")
    cli_parser.add_argument(
        "--dry",
        action="store_true",
        help="Dry run: orchestration plan + events only, no model calls (verifies "
        "event flow and the degradation chain)",
    )
    cli_parser.add_argument(
        "--events", help="Event log path (team mode). Default: RESULTS/events_cli_<ts>.jsonl"
    )

    return parser


def launch_gui(args) -> int:
    """Launch GUI interface."""
    try:
        from PySide6.QtWidgets import QApplication

        from transcoder.gui import MainWindow

        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        return app.exec()
    except ImportError:
        print("GUI requires PySide6. Install with: pip install transcoder[gui]")
        return 1


def launch_web(args) -> int:
    """Launch web server."""
    from transcoder.app import create_app

    app = create_app()

    if args.production:
        from waitress import serve

        print(f"Starting TransCoder production server on http://{args.host}:{args.port}")
        serve(app, host=args.host, port=args.port)
    else:
        print(f"Starting TransCoder development server on http://{args.host}:{args.port}")
        app.run(host=args.host, port=args.port, debug=args.debug)

    return 0


def run_cli(args) -> int:
    """Run CLI translation."""
    import json
    import time
    from pathlib import Path

    from transcoder.api import TransCoderAPI
    from transcoder.orchestrator import EventLog

    # Read input file
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return 1

    source_text = input_path.read_text(encoding="utf-8")
    target_langs = [lang.strip() for lang in args.target_langs.split(",")]

    unified = getattr(args, "run_mode", None)

    if unified == "team" or (unified is None and args.translator_endpoint):
        return run_team_cli(args, source_text, target_langs)

    if unified in ("direct", "reflection", "iterative"):
        # Unified naming maps onto the existing single-model mechanisms.
        mode_map = {"direct": "simple", "reflection": "reflect", "iterative": "iterate"}
        args.mode_type = mode_map[unified]
        if unified == "iterative":
            args.iterations = args.team_rounds  # reuse the rounds knob as iteration count
    mode_type = args.mode_type

    # Determine model based on provider
    model = args.model
    if model is None:
        model = "qwen3:0.6b" if args.provider == "ollama" else "gpt-4o-mini"

    # Initialize API with provider
    api = TransCoderAPI(model=model, provider_type=args.provider)

    # Run translation
    if not args.quiet:
        provider_name = "Ollama" if args.provider == "ollama" else "OpenAI"
        print(f"Translating with {provider_name} ({model}) from {args.source_lang} to {target_langs}...")

    result = api.translate(
        source_text=source_text,
        source_lang=args.source_lang,
        target_langs=target_langs,
        mode=mode_type,
        use_vector_db=args.use_vector_db,
        use_terminology=args.use_terminology,
        iterations=args.iterations,
    )

    if not result.success:
        print(f"Error: {result.error}", file=sys.stderr)
        return 1

    # Output results
    if args.output:
        output_path = Path(args.output)
        if args.json_output:
            output_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            lines = []
            for lang, trans in result.data.get("translations", {}).items():
                lines.append(f"=== {lang} ===")
                lines.append(trans.get("text", ""))
                lines.append("")
            output_path.write_text("\n".join(lines), encoding="utf-8")
        if not args.quiet:
            print(f"Output written to: {args.output}")
    else:
        if args.json_output:
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        else:
            for lang, trans in result.data.get("translations", {}).items():
                print(f"\n=== {lang} ===")
                print(trans.get("text", ""))

    return 0


def run_team_cli(args, source_text: str, target_langs: list) -> int:
    """Team mode (P3): multi-agent orchestration with event log + degradation."""
    import json
    import time
    from pathlib import Path

    from transcoder.api import TransCoderAPI
    from transcoder.orchestrator import EventLog
    from transcoder.team_setup import build_team_from_endpoints

    translator_endpoint = args.translator_endpoint
    if not translator_endpoint:
        print("Error: --mode team requires --translator-endpoint (or use --reviewer-endpoint only "
              "for online generation; see --help)", file=sys.stderr)
        return 1

    api_kwargs = {}
    terminology = vector_db = None
    local_api = None
    if args.use_terminology or args.use_vector_db:
        local_api = TransCoderAPI(model=args.translator_model or "qwen3:0.6b",
                                  provider_type="ollama", ollama_host="http://localhost:11434")
        if args.use_terminology:
            terminology = local_api.terminology
        if args.use_vector_db:
            vector_db = local_api.vector_db

    events_path = Path(args.events) if args.events else (
        Path(__file__).resolve().parent.parent / "RESULTS" / f"events_cli_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
    )
    event_log = EventLog(path=events_path)

    results = {}
    for target_lang in target_langs:
        orchestrator = build_team_from_endpoints(
            translator_endpoint=translator_endpoint,
            translator_model=args.translator_model,
            reviewer_endpoint=args.reviewer_endpoint,
            reviewer_model=args.reviewer_model,
            terminology_service=terminology,
            vector_db_service=vector_db,
            local_fallback=local_api.translation_service if local_api is not None else None,
            max_rounds=max(1, args.team_rounds),
            event_log=event_log,
            seed=args.seed,
        )
        team_result = orchestrator.run(source_text, args.source_lang, target_lang, dry=args.dry)
        dict_out = team_result.to_dict()
        dict_out["event_log"] = str(events_path)
        results[target_lang] = dict_out

        if not args.quiet:
            print(f"\n=== {target_lang} ===")
            print(team_result.final_translation or "(empty)")
            if team_result.degraded:
                print(f"  [degraded] {team_result.degraded_reason} -> local self-reflection", file=sys.stderr)
            for r in team_result.rounds:
                rev = r.get("review") or {}
                if rev.get("scores"):
                    print(f"  [round {r.get('round')}] scores={rev.get('scores')} pass={rev.get('passed')} "
                          f"issues={len(rev.get('issues') or [])}", file=sys.stderr)

    payload = {"mode": "team", "dry": args.dry, "event_log": str(events_path), "translations": results}
    if args.output:
        Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"Output written to: {args.output}")
    elif args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.quiet:
        pass

    return 0


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Default to GUI if no mode specified
    if args.mode is None:
        args.mode = "web"

    if args.mode == "gui":
        return launch_gui(args)
    elif args.mode == "web":
        return launch_web(args)
    elif args.mode == "cli":
        return run_cli(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
