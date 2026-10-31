# -*- coding: utf-8 -*-
"""Download the four edge-candidate small models from ModelScope (P6 edge probe).

Models are stored in the modelscope cache (~/.cache/modelscope). This script
only downloads; it does not modify anything outside its own RESULTS dir.
Writes RESULTS/edge_download_log.json with per-model status (honest record).

Usage: python3 RESULTS/tools/fetch_edge_models.py [name ...]
"""
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RESULTS = REPO / "RESULTS"

CANDIDATES = {
    "qwen3:0.6b": ["Qwen/Qwen3-0.6B"],
    "lfm2.5-350m": ["LiquidAI/LFM2.5-350M", "LiquidAI/LFM2-350M"],
    "granite4:350m-h": ["ibm-granite/granite-4.0-h-350m", "ibm-granite/granite-4.0-350m"],
    "gemma3:270m": ["google/gemma-3-270m-it"],
}


def fetch(tag: str, repos: list) -> dict:
    from modelscope import snapshot_download
    out = {"tag": tag, "repos_tried": []}
    for repo in repos:
        t0 = time.time()
        try:
            path = snapshot_download(repo)
            out.update({"repo": repo, "path": path, "ok": True,
                        "secs": round(time.time() - t0, 1)})
            return out
        except Exception as e:
            out["repos_tried"].append({"repo": repo, "error": f"{type(e).__name__}: {str(e)[:300]}"})
    out["ok"] = False
    return out


def main() -> int:
    tags = sys.argv[1:] or list(CANDIDATES)
    log_path = RESULTS / "edge_download_log.json"
    log = {}
    if log_path.exists():
        log = json.loads(log_path.read_text(encoding="utf-8"))
    for tag in tags:
        if tag in log and log[tag].get("ok"):
            print(f"[skip] {tag} already downloaded")
            continue
        print(f"[fetch] {tag} ...", flush=True)
        res = fetch(tag, CANDIDATES[tag])
        log[tag] = res
        log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[done] {tag}: ok={res.get('ok')} repo={res.get('repo')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())