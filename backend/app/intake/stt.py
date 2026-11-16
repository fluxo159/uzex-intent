from __future__ import annotations

import hashlib
import io
import json
import os
import threading
from pathlib import Path

import httpx

try:
    from app import config as _cfg
    ROOT = Path(_cfg.ROOT)
    offline = _cfg.offline
    STT_TIMEOUT_S = float(getattr(_cfg, "LLM_TIMEOUT_S", 8.0))
except Exception:  # pragma: no cover
    ROOT = Path(__file__).resolve().parents[3]
    STT_TIMEOUT_S = 8.0

    def offline() -> bool:
        return os.environ.get("DEMO_OFFLINE", "0") == "1"

CACHE_DIR = ROOT / "data" / "cache" / "intake" / "stt"
ELEVEN_MODEL = os.environ.get("ELEVENLABS_STT_MODEL", "scribe_v2")
WHISPER_MODEL_GPU = "medium"
WHISPER_MODEL_CPU = "small"
WHISPER_ALLOW_DOWNLOAD = os.environ.get("WHISPER_ALLOW_DOWNLOAD", "0") == "1"
WHISPER_COMPUTE_CUDA = os.environ.get("WHISPER_COMPUTE", "int8_float16")
MAX_AUDIO_BYTES = 20 * 1024 * 1024

TURKIC_TO_UZ = {"kk", "tr", "tk", "az", "ky", "tt", "ba", "ug"}
_ELEVEN_LANG = {"uz": "uzb", "ru": "rus"}
_ELEVEN_BACK = {"uzb": "uz", "rus": "ru", "uz": "uz", "ru": "ru"}

def map_lang(code: str | None) -> str | None:
    if not code:
        return None
    c = code.lower()[:3]
    if c in _ELEVEN_BACK:
        return _ELEVEN_BACK[c]
    c2 = c[:2]
    if c2 in ("uz", "ru"):
        return c2
    if c2 in TURKIC_TO_UZ or c in ("kaz", "tur", "tuk", "aze", "kir", "tat"):
        return "uz"
    return c2

def _cache_path(h: str, lang_hint: str | None) -> Path:
    return CACHE_DIR / f"{h}_{lang_hint or 'auto'}.json"

def _cache_get(h: str, lang_hint: str | None) -> dict | None:
    for p in (_cache_path(h, lang_hint), _cache_path(h, None)):
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
    return None

def _cache_put(h: str, lang_hint: str | None, res: dict) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(h, lang_hint).write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass

class STTError(Exception):
    pass

def eleven_transcribe(audio: bytes, lang_hint: str | None, filename: str = "audio.webm") -> dict:
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise STTError("no_key")
    data = {"model_id": ELEVEN_MODEL}
    if lang_hint in _ELEVEN_LANG:
        data["language_code"] = _ELEVEN_LANG[lang_hint]
    r = httpx.post("https://api.elevenlabs.io/v1/speech-to-text", headers={"xi-api-key": key},
                   data=data, files={"file": (filename, audio)}, timeout=STT_TIMEOUT_S)
    if r.status_code != 200:
        raise STTError(f"http_{r.status_code}")
    j = r.json()
    text = (j.get("text") or "").strip()
    return {"transcript": text, "lang": map_lang(j.get("language_code")) or lang_hint, "source": "elevenlabs"}

_whisper = None
_whisper_lock = threading.Lock()

def _cuda_available() -> bool:
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False

def whisper_config(cuda: bool | None = None) -> dict:
    cuda = _cuda_available() if cuda is None else cuda
    default = WHISPER_MODEL_GPU if cuda else WHISPER_MODEL_CPU
    return {
        "model": os.environ.get("WHISPER_MODEL", "").strip() or default,
        "device": "cuda" if cuda else "cpu",
        "compute_type": WHISPER_COMPUTE_CUDA if cuda else "int8",
    }

def _get_whisper():
    global _whisper
    with _whisper_lock:
        if _whisper is None:
            try:
                from faster_whisper import WhisperModel
                from faster_whisper.utils import download_model
            except Exception as e:
                raise STTError("whisper_not_installed") from e
            cfg = whisper_config()
            path = cfg["model"]
            if not os.path.isdir(path):
                try:
                    path = download_model(path, local_files_only=not WHISPER_ALLOW_DOWNLOAD)
                except Exception as e:
                    raise STTError("whisper_model_missing") from e
            try:
                _whisper = WhisperModel(path, device=cfg["device"], compute_type=cfg["compute_type"])
            except Exception as e:
                raise STTError("whisper_load_failed") from e
        return _whisper

def whisper_transcribe(audio: bytes, lang_hint: str | None) -> dict:
    try:
        model = _get_whisper()
    except STTError:
        raise
    except Exception as e:  # pragma: no cover
        raise STTError("whisper_load_failed") from e
    lang = lang_hint if lang_hint in ("uz", "ru") else None

    def run(language):
        segs, info = model.transcribe(io.BytesIO(audio), language=language, beam_size=5, vad_filter=True)
        return " ".join(s.text.strip() for s in segs).strip(), info

    try:
        text, info = run(lang)
        detected = getattr(info, "language", None)
        mapped = lang or map_lang(detected)
        if lang is None and mapped == "uz" and detected != "uz":
            text, _ = run("uz")
        if lang is None and mapped not in ("uz", "ru"):
            mapped = "ru"
    except Exception as e:
        raise STTError("whisper_failed") from e
    return {"transcript": text, "lang": mapped, "source": "whisper"}

OPENAI_STT_MODEL = os.environ.get("OPENAI_STT_MODEL", "gpt-transcribe")

def openai_transcribe(audio: bytes, lang_hint: str | None, filename: str = "audio.webm") -> dict:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise STTError("no_key")
    whisper_family = OPENAI_STT_MODEL.startswith("whisper")
    data = {"model": OPENAI_STT_MODEL, "response_format": "verbose_json" if whisper_family else "json"}
    if whisper_family:
        data["temperature"] = "0"
        if lang_hint in ("uz", "ru"):
            data["language"] = lang_hint
    elif lang_hint in ("uz", "ru"):
        data["prompt"] = "Oʻzbekcha yoki ruscha: tsement, tonna, narx, viloyat." if lang_hint == "uz" else "Русский: цемент, тонны, цена, область."
    r = httpx.post("https://api.openai.com/v1/audio/transcriptions", headers={"Authorization": f"Bearer {key}"},
                   data=data, files={"file": (filename, audio)}, timeout=STT_TIMEOUT_S)
    if r.status_code != 200:
        raise STTError(f"http_{r.status_code}")
    j = r.json()
    text = (j.get("text") or "").strip()
    lang = str(j.get("language") or "").lower()
    lang = {"uzbek": "uz", "russian": "ru", "uz": "uz", "ru": "ru"}.get(lang, lang_hint)
    return {"transcript": text, "lang": lang, "source": "openai"}

BACKENDS = {"openai": openai_transcribe, "elevenlabs": eleven_transcribe, "whisper": whisper_transcribe}

def transcribe(audio_bytes: bytes | None, lang_hint: str | None = None, filename: str = "audio.webm") -> dict:
    if lang_hint not in ("uz", "ru"):
        lang_hint = None
    if not audio_bytes:
        return {"transcript": "", "lang": lang_hint, "source": "none", "error": "empty_audio"}
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        return {"transcript": "", "lang": lang_hint, "source": "none", "error": "audio_too_large"}
    h = hashlib.sha256(audio_bytes).hexdigest()
    hit = _cache_get(h, lang_hint)
    if hit is not None:
        return {**hit, "cached": True}
    order = ["whisper"] if offline() else ["openai", "elevenlabs", "whisper"]
    errors: list[str] = []
    reason = "no_backend"
    for name in order:
        fn = BACKENDS.get(name)
        if fn is None:
            continue
        try:
            res = fn(audio_bytes, lang_hint, filename) if name in ("elevenlabs", "openai") else fn(audio_bytes, lang_hint)
        except (STTError, httpx.HTTPError, ValueError, KeyError) as e:
            errors.append(f"{name}:{e}")
            if isinstance(e, STTError) and str(e) != "no_key":
                reason = str(e)
            elif isinstance(e, httpx.HTTPError):
                reason = "network_error"
            continue
        if not res.get("transcript"):
            errors.append(f"{name}:empty")
            continue
        _cache_put(h, lang_hint, res)
        return res
    return {"transcript": "", "lang": lang_hint, "source": "none", "error": "stt_unavailable",
            "reason": reason, "details": errors}
