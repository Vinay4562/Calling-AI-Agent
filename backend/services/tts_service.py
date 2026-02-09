"""
Text-to-Speech Service - ElevenLabs integration for converting AI text to voice audio.
Supports Telugu and English with multilingual model.
"""
import base64
import logging
import uuid
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


class TTSService:
    def __init__(self):
        self.client = None
        self._initialized = False

    def _init_client(self):
        """Initialize ElevenLabs client."""
        if self._initialized:
            return True

        if not settings.is_elevenlabs_configured():
            logger.warning("ElevenLabs not configured. TTS will use fallback.")
            return False

        try:
            from elevenlabs import ElevenLabs
            self.client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
            self._initialized = True
            logger.info("ElevenLabs TTS client initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize ElevenLabs: {e}")
            return False

    async def generate_speech(self, text: str, language: str = "english") -> Optional[dict]:
        """
        Generate speech audio from text using ElevenLabs.
        Returns dict with audio_id, audio_base64, and content_type.
        """
        if not self._init_client():
            logger.warning("TTS not available. Returning None.")
            return None

        try:
            voice_id = settings.ELEVENLABS_VOICE_ID or "21m00Tcm4TlvDq8ikWAM"  # Default Rachel voice

            audio_generator = self.client.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id="eleven_multilingual_v2",
                voice_settings={
                    "stability": 0.7,
                    "similarity_boost": 0.8,
                    "style": 0.3,
                    "use_speaker_boost": True
                }
            )

            audio_data = b""
            for chunk in audio_generator:
                audio_data += chunk

            audio_id = str(uuid.uuid4())
            audio_b64 = base64.b64encode(audio_data).decode()

            logger.info(f"Generated TTS audio: {audio_id} ({len(audio_data)} bytes)")
            return {
                "audio_id": audio_id,
                "audio_base64": audio_b64,
                "audio_data": audio_data,
                "content_type": "audio/mpeg",
                "size": len(audio_data)
            }
        except Exception as e:
            logger.error(f"Error generating TTS: {e}")
            return None

    async def get_voices(self) -> list:
        """List available ElevenLabs voices."""
        if not self._init_client():
            return []

        try:
            voices_response = self.client.voices.get_all()
            return [
                {"voice_id": v.voice_id, "name": v.name}
                for v in voices_response.voices
            ]
        except Exception as e:
            logger.error(f"Error fetching voices: {e}")
            return []


tts_service = TTSService()
