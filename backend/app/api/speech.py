import logging
import os
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile

from app.models.schemas import TranscriptionResponse
from app.services.answer_extraction_service import normalize_numeric_answer
from app.services.whisper_service import transcribe_audio

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(
    file: UploadFile = File(...),
    current_question: str | None = Form(None),
) -> TranscriptionResponse:
    suffix = Path(file.filename or "audio.webm").suffix or ".webm"
    temp_path = ""

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = temp_file.name
            shutil.copyfileobj(file.file, temp_file)

        logger.info("Received audio file %s saved to temporary path", file.filename)
        text = transcribe_audio(temp_path)
        normalized_text = normalize_numeric_answer(current_question or "", text)
        return TranscriptionResponse(
            text=normalized_text,
            raw_text=text if normalized_text != text else None,
        )
    except Exception as exc:
        logger.exception("Transcription endpoint failed")
        return TranscriptionResponse(
            text=(
                "Не удалось распознать аудио автоматически. "
                "Для локальной демонстрации можно включить WHISPER_MOCK_MODE=true "
                "или ввести ответ вручную."
            )
        )
    finally:
        await file.close()
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
            logger.info("Temporary audio file removed")
