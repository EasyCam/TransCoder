# -*- coding: utf-8 -*-
"""P6 edge probe (task 6): existence, load, tok/s with the model's OWN tokenizer,
plus a spot translation test. Writes RESULTS/edge_models.json. Honest record."""

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "RESULTS" / "tools"))

from fetch_edge_models import CANDIDATES  # noqa: E402


def probe_model(tag, prompt_msgs, max_new=200):
    from transcoder.edge_local import EdgeTransformersProvider

    log_path = REPO / "RESULTS" / "edge_download_log.json"
    log = json.loads(log_path.read_text(encoding="utf-8"))
    entry = log.get(tag) or {}
    if not entry.get("ok"):
        return {"tag": tag, "status": "not_downloaded", "detail": entry}
    prov = EdgeTransformersProvider(model_path=entry["path"], model_tag=tag, max_new_tokens=max_new)
    t0 = time.time()
    try:
        tok = prov.tokenizer()
        n_params = sum(p.numel() for p in prov._model.parameters())
    except Exception as e:
        return {"tag": tag, "status": "load_failed", "error": f"{type(e).__name__}: {str(e)[:300]}",
                "load_secs": round(time.time() - t0, 1)}
    text, usage = prov.chat(prompt_msgs, temperature=0.3, max_new_tokens=max_new)
    tok_s = usage.get("tok_s")
    return {
        "tag": tag, "repo": entry["repo"], "status": "ok",
        "path": entry["path"], "params": n_params, "<=1b": n_params < 1_000_000_000,
        "load_secs": prov.load_secs,
        "spot_prompt": prompt_msgs[-1]["content"][:60],
        "spot_output": text[:300],
        "spot_tok_s": tok_s, "spot_completion_tokens": usage.get("completion_tokens"),
        "gen_log": prov.gen_log,
    }


def main():
    from transformers import __version__ as tv, AutoConfig  # noqa

    zh_prompt = [{"role": "user", "content": "将下面的中文翻译成英文，只输出译文：\n未庄的人都说阿Q阔了。"}]
    ja_prompt = [{"role": "user", "content": "次の中国語を日本語に翻訳してください。訳文のみ出力：\n上善は水のごとし。"}]
    out = {"date": "2026-10-19", "runtime": "transformers CPU (Apple M4, no GPU/llama.cpp)",
           "models": {}}
    for tag in CANDIDATES:
        print(f"[edge probe] {tag} ...", flush=True)
        rec = probe_model(tag, zh_prompt)
        if rec.get("status") == "ok":
            rec2 = probe_model(tag, ja_prompt, max_new=80)
            rec["spot_output_ja"] = rec2.get("spot_output", "")[:150]
            rec["spot_tok_s_ja"] = rec2.get("spot_tok_s")
            # drop bulky gen_log duplicates
            rec.pop("gen_log", None)
        out["models"][tag] = rec
        print(json.dumps(rec, ensure_ascii=False, default=str)[:400], flush=True)

    out_path = REPO / "RESULTS" / "edge_models.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("->", out_path)


if __name__ == "__main__":
    main()