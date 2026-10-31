# -*- coding: utf-8 -*-
"""Build RESULTS/corpus/dataset.json (P6 corpus, pre-registered before runs 2026-10-19).

Sources (all public-domain, with proven recorded):
- 道德經 received text: zh.wikisource 「道德真經」(正统道藏), fetched 2026-10-19;
  refs: Legge 1891 (PG #216), Stanislas Julien 1842 (fr.wikisource), 井上秀天 1915
  書き下し (ja.wikisource「老子道徳経」, classical register).
- 阿Q正传 (local PD file 金明哲 lecture dir) ↔ George Kin Leung 1927 en.wikisource
  (aligned at paragraph boundaries verified manually).
- C2 excerpts from MTMinePy experiments/multilingual (no references).
- C3 self-written technical passages + glossary injection (no references).
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TMP = Path("/tmp")
MULTI = Path("/Users/fred/Documents/GitHub/EasyCam/MTMinePy/experiments/multilingual")
LU = Path("/Users/fred/Documents/重点文献/金明哲教授的文件夹/05_吉外讲座/第一讲/Lu_阿Q正传.txt")
OUT = REPO / "RESULTS" / "corpus"

GLOS = {
    "大语言模型": {"en": "large language model", "ja": "大規模言語モデル",
          "fr": "grand modèle de langage", "de": "großes Sprachmodell"},
    "检索增强生成": {"en": "retrieval-augmented generation", "ja": "検索拡張生成"},
    "词元": {"en": "token", "ja": "トークン", "fr": "jeton (token)", "de": "Token"},
    "多智能体": {"en": "multi-agent", "ja": "マルチエージェント", "fr": "multi-agents"},
}

PAIRS = []


def clean_ref(t: str) -> str:
    if not t:
        return t
    t = re.sub(r"\s+", " ", t.replace(">", " ")).strip()
    t = re.sub(r"^CHAPITRE\s+[IVXLC]+\.\s*", "", t)
    t = re.sub(r"^Ch\.\s*\d+\.\s*", "", t)
    t = re.sub(r"^\d+\.\s+", "", t, count=1)
    return t.strip()


def add(pair_id, subset, src, tgt_lang, ref=None, ref_prov=None, src_lang="zh-cn", target_text=None):
    PAIRS.append({
        "pair_id": pair_id, "subset": subset,
        "source_text": src, "source_lang": src_lang, "target_lang": tgt_lang,
        "reference": clean_ref(ref) if ref else None,
        "reference_provenance": ref_prov or ("公版参考译文" if ref else None),
    })


# --------------------------- C1-la: 道德經 -------------------------------- #
zh_tx = (TMP / "ws_zh_daodejing_daozhen.txt").read_text(encoding="utf-8")

def _zh_header_positions():
    pat = re.compile(r"[一-龥]{1,5}章第[一二三四五六七八九十百]+\n\n")
    return [(mm.start(), mm.end(), mm.group(0)) for mm in pat.finditer(zh_tx)]


_ZH_HEADERS = _zh_header_positions()


def _zh_header_idx(n: int) -> int:
    for idx, (_s, _e, h) in enumerate(_ZH_HEADERS):
        if re.fullmatch(r"[一-龥]{1,5}章第" + NUM_CN[n] + r"\n\n", h):
            return idx
    return -1


def zh_chapter(n):
    """Extract chapter n (received text); headers like 易性章第八 (some glued to
    previous content in the source page, hence capped-length name matching)."""
    idx = _zh_header_idx(n)
    if idx < 0:
        return None
    start = _ZH_HEADERS[idx][1]
    next_start = _ZH_HEADERS[idx + 1][0] if idx + 1 < len(_ZH_HEADERS) else len(zh_tx)
    return re.sub(r"\s+", "", zh_tx[start:next_start]).strip()

CH_NUMS = [1, 8, 9, 15]
NUM_CN = {1: "一", 8: "八", 9: "九", 15: "十五"}
LEGGE_KEYS = {1: "legge_ch1_en", 8: "legge_ch8_en", 9: "legge_ch9_en", 15: "legge_ch15_en"}

legge = (TMP / "pg216.txt").read_text(encoding="utf-8")

def legge_ch(n):
    start_str = f"{n}. 1. " if n > 1 else "1. 1. "
    if n == 1:
        s = legge.find("Ch. 1. 1. The Tao that can be trodden")
    else:
        s = legge.find(start_str)
    if s < 0:
        return None
    # end at next chapter marker "N+1. 1." (beware false inside text)
    nxt = re.search(r"(?m)^\s*" + str(n + 1) + r"\.\s+1\.\s", legge[s + 10:])
    seg = legge[s + len(start_str): s + 10 + nxt.start()] if nxt else legge[s:s + 1500]
    seg = re.sub(r"Ch\.\s*", "", seg)
    return re.sub(r"\s+", " ", seg).strip()

julien = json.loads((TMP / "julien_chapters.json").read_text(encoding="utf-8"))
ja_tx = (TMP / "ws_ja_kundoku.txt").read_text(encoding="utf-8")

def ja_chapter(n):
    i = ja_tx.find(f"=={NUM_CN[n]}章=")
    if i < 0:
        return None
    nxt_i = ja_tx.find("=", i + 10)
    # next chapter header like ==二章=
    nxt = re.search(rf"==[一二三四五六七八九十]+章=", ja_tx[i + 10:])
    seg = ja_tx[i + len(f"=={NUM_CN[n]}章="): i + 10 + nxt.start()] if nxt else ja_tx[i:i + 1500]
    m = re.search(r"\{\{\*\|(.*?)\}\}", seg, flags=re.S)
    if not m:
        return None
    txt = m.group(1)
    txt = re.sub(r"\{\{re\}\}", "", txt)
    txt = re.sub(r"\{\{\d\}\}", "", txt)
    return txt.strip()

for n in CH_NUMS:
    zh = zh_chapter(n)
    print(f"--- ch{n} zh ({len(zh or '')} chars): {(zh or 'MISSING')[:60]}")
    refs = {
        "en": (legge_ch(n), f"James Legge trans. 1891, The Tao Teh King (PG #216), ch.{n}"),
        "fr": ((julien.get(str(n)) or "").strip(), f"Stanislas Julien trans. 1842, fr.wikisource, ch.{n}"),
        "ja": (ja_chapter(n), "井上秀天『老子の新研究』1915 書き下し文 (公版), ja.wikisource; kundoku register"),
    }
    for lang, (ref, prov) in refs.items():
        assert lang in ("en", "fr", "ja")
        add(f"la-ch{n}-{lang}", "c1-la", zh, lang, ref if ref else None, prov, src_lang="zh-classical-cn")
    for lang in ("ko", "de"):
        add(f"la-ch{n}-{lang}", "c1-la", zh, lang, None, "无参考：未获公版权威译本（ko/de 道德经译文未核实可得）", src_lang="zh-classical-cn")

# --------------------------- C1-aq: 阿Q正传 ------------------------------- #
lu = LU.read_text(encoding="utf-8")
xu_end = lu.find("以上可以算是序。")
aq_xu = lu[: lu.find("。", lu.find("仿佛思想里有鬼似的")) + 1]
aq_xu = re.sub(r"\s+", "", aq_xu)
leung1 = (TMP / "leung_ch1_en.txt").read_text(encoding="utf-8")
p = leung1.find("FOR more than a year or two")
leung1_p1 = leung1[p: leung1.find("goading me to the task.") + len("goading me to the task.")]
leung1_p1 = re.sub(r"\s+", " ", leung1_p1).strip()

add("aq-xu-en", "c1-aq", aq_xu, "en", leung1_p1,
    "George Kin Leung trans. 1927 (en.wikisource), foreword ¶1 (paragraph-aligned)")
for lang in ("ja", "ko", "fr", "de"):
    add(f"aq-xu-{lang}", "c1-aq", aq_xu, lang, None, f"无参考：未获公版权威译本（{lang}）")

leung2 = (TMP / "leung_ch2_en.txt").read_text(encoding="utf-8")
p2 = leung2.find("NOT only are the surname")
leung2_p1 = leung2[p2: leung2.find("anyway!") + len("anyway!")]
leung2_p1 = re.sub(r"\s+", " ", leung2_p1)
ch1_start = xu_end + len("以上可以算是序。")
aq_ch1 = lu[ch1_start: lu.find("！』", ch1_start) + len("！』")]
aq_ch1 = re.sub(r"\s+", "", aq_ch1)
add("aq-ch1-en", "c1-aq", aq_ch1, "en", leung2_p1,
    "George Kin Leung trans. 1927 (en.wikisource), Ch. II ¶1 (paragraph-aligned)")
for lang in ("ja", "ko", "fr", "de"):
    add(f"aq-ch1-{lang}", "c1-aq", aq_ch1, lang, None, f"无参考：未获公版权威译本（{lang}）")

# --------------------------- C2: 现代短文（无参考） ----------------------- #
def excerpt(fname, n_chars=300, skip_head=200):
    t = (MULTI / fname).read_text(encoding="utf-8")
    t = re.sub(r"\s+", " ", t)[skip_head: skip_head + n_chars]
    return t.strip()


def sentence_window(fname, approx_start=600, n_chars=320):
    """Contiguous whole-sentence window starting near approx_start."""
    raw = (MULTI / fname).read_text(encoding="utf-8")
    t = re.sub(r"\s+", " ", raw)
    start = approx_start
    # advance to the first sentence-start after a period
    for m in re.finditer(r"(?<=\. )[A-ZÀ-ÖØ-ÞÁÉÍÓÚ„„']", t[: start + n_chars]):
        if m.start() >= approx_start - 120:
            start = m.start()
            break
    chunk = t[start: start + n_chars]
    # end at the last full stop
    ends = [mm.end() for mm in re.finditer(r"[.!?«»\"]\s", chunk)]
    if ends:
        chunk = chunk[: ends[-1]].strip()
    return chunk

C2 = [
    ("c2-en-zh", "en", 600),
    ("c2-fr-zh", "fr", 600),
    ("c2-de-zh", "de", 1200),
]
lu_modern = []
for para in lu.split("\n"):
    pass
aq_body = lu[xu_end:]
# modern zh source excerpts from Ah Q body (contiguous), cleaned
aq_zh1 = re.sub(r"\s+", "", aq_body[aq_body.find("阿Q没有家"): aq_body.find("阿Q没有家") + 230])
aq_zh2_anchor = aq_body.find("然而阿Q在形式上打败了")
if aq_zh2_anchor < 0:
    aq_zh2_anchor = aq_body.find("阿Q在形式上打败了")
aq_zh2 = re.sub(r"\s+", "", aq_body[aq_zh2_anchor: aq_zh2_anchor + 230])
add("c2-zh-en", "c2", aq_zh1, "en", None, "无参考（C2 设计：仅报无参考指标）；源=《阿Q正传》第一章节选（公版）")
add("c2-zh-fr", "c2", aq_zh2, "fr", None, "无参考（C2 设计：仅报无参考指标）；源=《阿Q正传》第一章节选（公版）")
for pid, slang, anchor in C2:
    add(pid, "c2", sentence_window(f"{slang}.txt", anchor), "zh-cn", None,
        f"无参考（C2 设计；源文 = MTMinePy multilingual/{slang}.txt 公版文学节选，整句窗口）", src_lang=slang)
# ja→zh 方向剔除并留痕：ja.txt 为双栏 OCR 交错排版，无干净连续日文段（provenance 原因），
# ja 语向已由 C1-la（書き下し参考）与 C1-aq（无参考）覆盖。

# --------------------------- C3: 术语密集技术段（无参考） ----------------- #
C3 = [
    ("c3-tech1",
     "本系统采用检索增强生成（RAG）架构：大语言模型在回答之前先从向量数据库中检索"
     "相关文档片段，再把上下文拼接进提示词。词元计数使用真实 tokenizer，多智能体"
     "协作由编排器统一调度，术语守卫负责注入术语库中的推荐译法。"),
    ("c3-tech2",
     "端侧部署要求把大语言模型压缩到能放进手机内存的规模，同时保持词元生成速度。"
     "检索增强生成的缓存层在离线时仍可提供相似句召回，多智能体循环的重试次数上限"
     "由配置决定。"),
]
for pid, txt in C3:
    add(pid, "c3", txt, "en", None, "无参考（C3 术语密集段，触发 TerminologyGuard）")

# --------------------------- provenance & write --------------------------- #
dataset = {
    "schema": "transcoder-next/dataset/v1",
    "built": "2026-10-19",
    "note": "参考译文只使用公版/权威译本（来源见 reference_provenance）；其余语对无参考，"
            "只报长度比与评审得分（experiments-design §1/§6）。",
    "glossary": GLOS,
    "n_pairs": len(PAIRS),
    "n_with_reference": sum(1 for p in PAIRS if p["reference"]),
    "pairs": PAIRS,
}
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "dataset.json").write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"dataset: {len(PAIRS)} pairs, {dataset['n_with_reference']} with reference -> {OUT / 'dataset.json'}")