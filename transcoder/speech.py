"""Offline read-aloud module: TTS playback + pronunciation scoring.

- TTS: macOS ``say`` (Chinese system voices) rendered to m4a, cached by content.
- ASR: faster-whisper (base, multilingual, CPU int8) transcribes the learner.
- Scoring: character-level alignment (SequenceMatcher) marks every target
  character as correct / wrong / missing, plus accuracy & completeness.
"""

import hashlib
import re
import subprocess
import tempfile
import threading
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

AUDIO_DIR = Path(__file__).resolve().parent.parent / "data" / "audio"
_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")

PASSAGES: List[Dict[str, str]] = [
    {"id": "p1", "level": "HSK 2", "text": "今天天气很好，我们一起去公园散步。"},
    {"id": "p2", "level": "HSK 2", "text": "我每天早上七点起床，先刷牙，然后吃早饭。"},
    {"id": "p3", "level": "HSK 3", "text": "学习一门语言需要每天练习，不能着急。"},
    {"id": "p4", "level": "HSK 3", "text": "北京是中国北方的城市，冬天很冷，夏天很热。"},
    {"id": "p5", "level": "HSK 4", "text": "因为昨天下雨，所以我们没有去爬山，在家看电影。"},
    {"id": "p6", "level": "HSK 4", "text": "他不但会说汉语，而且写得一手好字。"},
    {"id": "p7", "level": "HSK 5", "text": "随着科技的发展，人们的生活方式发生了很大的变化。"},
    {"id": "p8", "level": "HSK 5", "text": "只有坚持练习，才能把发音说得又清楚又自然。"},
]

PASSAGES_EN: List[Dict[str, str]] = [
    {"id": "e1", "level": "PETS-5", "text": "Good morning. I would like to talk about the importance of daily practice in language learning. Reading aloud helps learners notice pronunciation problems that silent reading hides."},
    {"id": "e2", "level": "PETS-5", "text": "The city has changed a great deal over the past ten years. New libraries and parks have made public spaces more comfortable for families."},
    {"id": "e3", "level": "CET-6", "text": "Universities are increasingly offering online courses, which allow students to study at their own pace and review difficult materials repeatedly."},
    {"id": "e4", "level": "CET-4", "text": "Many people believe that a healthy diet and regular exercise are the two most effective ways to reduce stress in modern life."},
]

PASSAGES_JA: List[Dict[str, str]] = [
    {"id": "j1", "level": "JLPT N5", "text": "毎朝七時に起きて、顔を洗ってから朝ごはんを食べます。"},
    {"id": "j2", "level": "JLPT N4", "text": "日本語を勉強するために、毎日単語を覚えて、友達と会話の練習をしています。"},
    {"id": "j3", "level": "JLPT N3", "text": "週末は図書館へ行って本を読みます。静かな環境のほうが集中できるからです。"},
    {"id": "j4", "level": "JLPT N3", "text": "日本では、電車の中で携帯電話で話すのはマナーが悪いと考えられています。"},
]

PASSAGES_BY_LANG = {"zh": PASSAGES, "en": PASSAGES_EN, "ja": PASSAGES_JA}

_VOICE_CACHE: Optional[Dict[str, str]] = None
_MODEL = None
_MODEL_LOCK = threading.Lock()


def _chinese_voices() -> Dict[str, str]:
    """Map language prefix -> best available macOS voice."""
    global _VOICE_CACHE
    if _VOICE_CACHE is not None:
        return _VOICE_CACHE
    voices = {"zh": "Tingting", "en": "Samantha", "ja": "Kyoko"}
    try:
        out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=10).stdout
        names = set()
        for line in out.splitlines():
            parts = line.split()
            if parts:
                names.add(parts[0])
        for cand in ("Tingting", "Meijia", "Sinji", "Li-mu", "Eddy", "Flo", "Grandma"):
            if cand in names:
                voices["zh"] = cand
                break
        for cand in ("Samantha", "Alex", "Eddy"):
            if cand in names:
                voices["en"] = cand
                break
        for cand in ("Kyoko", "Otoya", "Eddy"):
            if cand in names:
                voices["ja"] = cand
                break
    except Exception:
        pass
    _VOICE_CACHE = voices
    return voices


def synthesize(text: str, lang: str = "zh", voice: Optional[str] = None) -> Dict[str, Any]:
    """Render text to an m4a file (cached). Returns file name + voice."""
    text = (text or "").strip()
    if not text:
        raise ValueError("text is required")
    voice = voice or _chinese_voices().get((lang or "zh")[:2], _chinese_voices()["zh"])
    digest = hashlib.sha1(f"{voice}|{text}".encode("utf-8")).hexdigest()[:20]
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    out = AUDIO_DIR / f"tts_{digest}.m4a"
    if not out.exists():
        with tempfile.TemporaryDirectory() as td:
            aiff = Path(td) / "tts.aiff"
            subprocess.run(
                ["say", "-v", voice, "-o", str(aiff), text],
                check=True, capture_output=True, timeout=90,
            )
            subprocess.run(
                ["afconvert", "-f", "m4af", "-d", "aac", str(aiff), str(out)],
                check=True, capture_output=True, timeout=90,
            )
    return {"file": out.name, "voice": voice, "bytes": out.stat().st_size}


def _get_model():
    global _MODEL
    if _MODEL is None:
        with _MODEL_LOCK:
            if _MODEL is None:
                from faster_whisper import WhisperModel

                _MODEL = WhisperModel("base", device="cpu", compute_type="int8")
    return _MODEL


def transcribe(audio_path: str, language: str = "zh") -> Dict[str, Any]:
    """Speech-to-text with faster-whisper; returns text + duration."""
    model = _get_model()
    segments, info = model.transcribe(audio_path, language=language, beam_size=1, vad_filter=True)
    text = "".join(seg.text for seg in segments).strip()
    return {"text": text, "language": info.language, "duration": round(float(info.duration), 2)}


try:  # simplified/traditional normalisation (whisper often emits traditional)
    from zhconv import convert as _zh_convert
except Exception:  # pragma: no cover - optional dependency
    _zh_convert = None


def _norm_char(ch: str) -> str:
    if _zh_convert is None or not _CJK.match(ch):
        return ch
    try:
        return _zh_convert(ch, "zh-cn")
    except Exception:
        return ch


_WORD_EN = re.compile(r"[A-Za-z']+")


def _to_hiragana(ch: str) -> str:
    o = ord(ch)
    if 0x30A1 <= o <= 0x30F6:
        return chr(o - 0x60)
    return ch


def _norm_key(ch: str, lang: str) -> str:
    if lang == "zh":
        return _norm_char(ch)
    if lang == "ja":
        return _to_hiragana(ch)
    return ch.lower()


def _units(text: str, lang: str) -> List[Dict[str, Any]]:
    """Scored units: English words, otherwise CJK characters."""
    out: List[Dict[str, Any]] = []
    if lang == "en":
        for m in _WORD_EN.finditer(text or ""):
            out.append({"text": m.group(0), "start": m.start(), "end": m.end(),
                        "key": m.group(0).lower()})
        return out
    if lang == "ja":
        try:
            import pykakasi

            kks = pykakasi.kakasi()
            cursor = 0
            for item in kks.convert(text or ""):
                orig = item.get("orig", "")
                if not orig:
                    continue
                start = (text or "").find(orig, cursor)
                if start < 0:
                    start = cursor
                hira = item.get("hira") or orig
                for kana_char in hira:
                    out.append({"text": orig, "start": start, "end": start + len(orig),
                                "key": kana_char})
                cursor = start + len(orig)
            if out:
                return out
        except Exception:
            pass
    for i, ch in enumerate(text or ""):
        if _CJK.match(ch) or ch.isalnum():
            out.append({"text": ch, "start": i, "end": i + 1, "key": _norm_key(ch, lang)})
    return out


def annotate(text: str, lang: str = "zh") -> Dict[str, Any]:
    """Reading aids: pinyin (zh), IPA (en), romaji/hiragana/katakana (ja)."""
    text = text or ""
    tokens: List[Dict[str, str]] = []
    if lang == "zh":
        from pypinyin import Style, lazy_pinyin

        for ch in text:
            if _CJK.match(ch):
                try:
                    tokens.append({"text": ch, "pinyin": lazy_pinyin(ch, style=Style.TONE)[0]})
                except Exception:
                    tokens.append({"text": ch, "pinyin": ""})
            else:
                tokens.append({"text": ch, "pinyin": ""})
    elif lang == "en":
        import eng_to_ipa

        last = 0
        for m in _WORD_EN.finditer(text):
            if m.start() > last:
                tokens.append({"text": text[last:m.start()], "ipa": ""})
            try:
                ipa = eng_to_ipa.convert(m.group(0))
            except Exception:
                ipa = ""
            tokens.append({"text": m.group(0), "ipa": ipa if ipa != m.group(0) + "*" else ""})
            last = m.end()
        if last < len(text):
            tokens.append({"text": text[last:], "ipa": ""})
    elif lang == "ja":
        import pykakasi

        kks = pykakasi.kakasi()
        for item in kks.convert(text):
            tokens.append({
                "text": item.get("orig", ""),
                "hira": item.get("hira", ""),
                "kata": item.get("kana", ""),
                "romaji": item.get("hepburn", ""),
            })
    return {"language": lang, "tokens": tokens}


def score_reading(target: str, transcript: str, language: str = "zh") -> Dict[str, Any]:
    """Pronunciation assessment at word level (en) or character level (zh/ja).

    correct = matched, wrong = substituted, missing = not read.
    """
    tgt = _units(target, language)
    hyp = _units(transcript, language)
    if not tgt:
        return {"error": "empty target", "items": [], "chars": [],
                "accuracy": 0.0, "completeness": 0.0, "score": 0.0}

    status = ["missing"] * len(tgt)
    sm = SequenceMatcher(None, [u["key"] for u in tgt], [u["key"] for u in hyp], autojunk=False)
    for tag, i1, i2, _j1, _j2 in sm.get_opcodes():
        if tag == "equal":
            for i in range(i1, i2):
                status[i] = "correct"
        elif tag == "replace":
            for i in range(i1, i2):
                status[i] = "wrong"
        elif tag == "delete":
            for i in range(i1, i2):
                status[i] = "missing"

    correct = status.count("correct")
    wrong = status.count("wrong")
    missing = status.count("missing")
    accuracy = correct / len(tgt) * 100.0
    completeness = (len(tgt) - missing) / len(tgt) * 100.0
    score = round((0.7 * accuracy + 0.3 * completeness), 1) / 10.0

    raw_items = [
        {"text": tgt[i]["text"], "start": tgt[i]["start"], "end": tgt[i]["end"],
         "status": status[i]}
        for i in range(len(tgt))
    ]
    # aggregate kana-level results back to their original token spans
    severity = {"correct": 0, "missing": 1, "wrong": 2}
    merged: Dict[Any, Dict[str, Any]] = {}
    for it in raw_items:
        k = (it["start"], it["end"])
        if k not in merged:
            merged[k] = dict(it)
        elif severity[it["status"]] > severity[merged[k]["status"]]:
            merged[k]["status"] = it["status"]
    items = sorted(merged.values(), key=lambda x: x["start"])
    return {
        "items": items,
        "chars": items,
        "total": len(tgt),
        "correct": correct,
        "wrong": wrong,
        "missing": missing,
        "accuracy": round(accuracy, 1),
        "completeness": round(completeness, 1),
        "score": round(score, 1),
        "transcript": transcript,
        "language": language,
    }


DIAG_SYSTEM = (
    "You are a pronunciation coach for language learners. Given the target text, the "
    "learner's ASR transcript, and the mismatched units, explain concretely what was "
    "likely mispronounced and how to fix it (tones for Chinese, phonemes for English, "
    "mora/katakana for Japanese). Reply ONLY with a JSON object:\n"
    '{"summary": "one or two sentences", "issues": [{"span": "target span", '
    '"problem": "what went wrong", "advice": "how to fix"}]}'
)


def diagnose_pronunciation(provider, model: str, target: str, transcript: str,
                           language: str = "zh", items=None, temperature: float = 0.3) -> Dict[str, Any]:
    """Ask the review model to explain the pronunciation mismatches."""
    from transcoder.agents import extract_json_block
    from transcoder.human_workbench import _call_provider

    diffs = [i.get("text", "") for i in (items or []) if i.get("status") in ("wrong", "missing")][:25]
    user = (f"Target ({language}):\n{target}\n\nHeard transcript:\n{transcript}\n\n"
            f"Mismatched units: {', '.join(diffs) if diffs else '(none)'}")
    messages = [{"role": "system", "content": DIAG_SYSTEM}, {"role": "user", "content": user}]
    try:
        raw, tokens_in, tokens_out = _call_provider(provider, messages, model, temperature)
    except Exception as e:
        return {"summary": "", "issues": [], "parse_ok": False, "error": str(e)}
    obj = extract_json_block(raw) or {}
    issues = [{
        "span": str(it.get("span", ""))[:120],
        "problem": str(it.get("problem", ""))[:300],
        "advice": str(it.get("advice", ""))[:300],
    } for it in (obj.get("issues") or [])[:12] if isinstance(it, dict)]
    return {
        "summary": str(obj.get("summary", "") or "")[:500],
        "issues": issues,
        "parse_ok": bool(obj),
        "error": None if obj else "could not parse model reply as JSON",
    }
