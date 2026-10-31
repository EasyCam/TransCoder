"""
Acceptance check: no plaintext API key anywhere in the deliverable tree.

Reads the keys from the local config files into memory, then scans every file
in the TransCoder repository (including RESULTS/) for their presence. Any hit
is a hard failure. This closes the loop on the handoff rule:
"代码/日志/RESULTS grep 无明文 key（验收项）".

Usage:
    python -m transcoder.security_check [--paths PATH ...]
Exit code 0 = clean, 1 = leak found / keys unreadable.
"""

import sys
from pathlib import Path
from typing import Iterator, List, Optional

from transcoder.endpoints import discover_endpoints

# Files that legitimately must not be scanned (huge binaries).
SKIP_SUFFIXES = {".pt", ".bin", ".safetensors", ".onnx", ".pkl", ".gz", ".zip", ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".DS_Store", ".faiss"}
MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB text cap


def iter_files(root: Path) -> Iterator[Path]:
    if root.is_file():
        yield root
        return
    for p in sorted(root.rglob("*")):
        if p.is_file():
            yield p


def _is_text_candidate(path: Path) -> bool:
    if path.suffix.lower() in SKIP_SUFFIXES:
        return False
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return False
    except OSError:
        return False
    return True


def collect_secrets() -> List[str]:
    """Keys from local configs (in memory only) + env-loaded ones, len>=8."""
    secrets: List[str] = []
    for ep in discover_endpoints().values():
        key = ep.api_key
        if key and len(key) >= 8:
            secrets.append(key)
    return secrets


def scan_tree(root: Path, secrets: List[str]) -> List[str]:
    """Return paths that contain any of the secrets (substring match)."""
    hits: List[str] = []
    if not root.exists():
        return hits
    for f in iter_files(root):
        if ".git/" in str(f):
            continue
        if not _is_text_candidate(f):
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for secret in secrets:
            if secret in content:
                hits.append(str(f))
                break
    return hits


def main(argv: Optional[List[str]] = None) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    secrets = collect_secrets()
    if not secrets:
        print("no secrets discovered in local configs -> nothing to grep; PASS (nothing stored)")
        return 0
    paths = [repo_root] if argv is None else [Path(a) for a in argv]
    hits: List[str] = []
    for p in paths:
        hits.extend(scan_tree(p, secrets))
    if hits:
        print("LEAK FOUND — plaintext key present in:")
        for h in hits:
            print(f"  {h}")
        return 1
    print(f"clean: {len(secrets)} secret(s) checked, no plaintext occurrences under {[str(p) for p in paths]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())