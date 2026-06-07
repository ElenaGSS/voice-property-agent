import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MODEL_NAME = "openai/whisper-small"
_pipeline: Any | None = None


def _is_mock_mode() -> bool:
    return os.getenv("WHISPER_MOCK_MODE", "").lower() in {"1", "true", "yes"}


def _load_pipeline() -> Any:
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    if _is_mock_mode():
        logger.info("Whisper mock mode enabled; model will not be loaded")
        return None

    logger.info("Loading Whisper model lazily: %s", MODEL_NAME)
    try:
        import torch
        from transformers import pipeline

        device = 0 if torch.cuda.is_available() else -1
        torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        _pipeline = pipeline(
            "automatic-speech-recognition",
            model=MODEL_NAME,
            torch_dtype=torch_dtype,
            device=device,
        )
        logger.info("Whisper model loaded successfully")
        return _pipeline
    except Exception as exc:
        logger.exception("Failed to load Whisper model")
        raise RuntimeError(
            "Whisper Small could not be loaded. For local demos, set WHISPER_MOCK_MODE=true."
        ) from exc


def transcribe_audio(audio_path: str | Path) -> str:
    if _is_mock_mode():
        return "Mock transcription: собственник описывает объект и свои ожидания."

    recognizer = _load_pipeline()
    logger.info("Transcribing audio file: %s", audio_path)
    try:
        result = recognizer(
            str(audio_path),
            generate_kwargs={"language": "russian", "task": "transcribe"},
        )
        text = result.get("text", "") if isinstance(result, dict) else str(result)
        return text.strip()
    except Exception as exc:
        logger.exception("Audio transcription failed")
        raise RuntimeError("Не удалось распознать аудио. Попробуйте ещё раз или включите mock mode.") from exc
