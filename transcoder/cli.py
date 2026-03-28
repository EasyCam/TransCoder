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
from typing import Optional


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
        """
    )
    
    # Unified flags
    parser.add_argument("-V", "--version", action="version", version=f"transcoder {__import__('transcoder').__version__}")
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
    cli_parser.add_argument("-t", "--target-langs", required=True, help="Target languages (comma-separated, e.g., en,ja,ko)")
    cli_parser.add_argument("-m", "--model", default="qwen3:0.6b", help="Ollama model to use")
    cli_parser.add_argument("--mode-type", choices=["simple", "stream", "reflect", "triple", "iterate"], 
                           default="simple", help="Translation mode")
    cli_parser.add_argument("--iterations", type=int, default=3, help="Iterations for iterate mode")
    cli_parser.add_argument("--use-vector-db", action="store_true", help="Use translation memory")
    cli_parser.add_argument("--use-terminology", action="store_true", help="Use terminology database")
    
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
    from pathlib import Path
    from transcoder.api import TransCoderAPI
    
    # Read input file
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return 1
    
    source_text = input_path.read_text(encoding="utf-8")
    target_langs = [lang.strip() for lang in args.target_langs.split(",")]
    
    # Initialize API
    api = TransCoderAPI(model=args.model)
    
    # Run translation
    if not args.quiet:
        print(f"Translating from {args.source_lang} to {target_langs}...")
    
    result = api.translate(
        source_text=source_text,
        source_lang=args.source_lang,
        target_langs=target_langs,
        mode=args.mode_type,
        use_vector_db=args.use_vector_db,
        use_terminology=args.use_terminology,
        iterations=args.iterations
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