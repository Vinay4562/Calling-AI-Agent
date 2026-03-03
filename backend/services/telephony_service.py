"""
Telephony Service - Twilio programmable voice for outbound calls to India.
Handles call initiation, TwiML generation, and call flow management.
"""
import logging
from typing import Optional
from twilio.twiml.voice_response import VoiceResponse, Gather
from config import settings

logger = logging.getLogger(__name__)


class TelephonyService:
    def __init__(self):
        self.client = None
        self._initialized = False

    def _init_client(self):
        """Initialize Twilio client."""
        if self._initialized:
            return True

        if not settings.is_twilio_configured():
            logger.warning("Twilio not configured.")
            return False

        try:
            from twilio.rest import Client
            self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            self._initialized = True
            logger.info("Twilio voice client initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Twilio: {e}")
            return False

    async def initiate_call(self, phone: str, session_id: str) -> Optional[str]:
        """
        Initiate an outbound call via Twilio.
        Returns the Twilio Call SID on success.
        """
        if not self._init_client():
            logger.error("Cannot initiate call: Twilio not configured")
            return None

        try:
            if not phone.startswith("+"):
                phone = f"+91{phone}"

            webhook_url = f"{settings.WEBHOOK_BASE_URL}/api/webhook/voice/answer?session_id={session_id}"
            status_url = f"{settings.WEBHOOK_BASE_URL}/api/webhook/voice/status?session_id={session_id}"

            call = self.client.calls.create(
                to=phone,
                from_=settings.TWILIO_PHONE_NUMBER,
                url=webhook_url,
                status_callback=status_url,
                status_callback_event=["initiated", "ringing", "answered", "completed"],
                status_callback_method="POST",
                method="POST",
                timeout=30,
                machine_detection="Enable"
            )

            logger.info(f"Call initiated: SID={call.sid}, to={phone}")
            return call.sid
        except Exception as e:
            logger.error(f"Error initiating call to {phone}: {e}")
            return None

    def generate_greeting_twiml(self, session_id: str, audio_url: Optional[str] = None, language: str = "english") -> str:
        """Generate TwiML for initial greeting with speech gathering."""
        response = VoiceResponse()

        if audio_url:
            response.play(audio_url)
        else:
            text = "Hello! Thank you for picking up. Is this a good time to talk?" if language.lower() == "english" else "నమస్కారం! మాట్లాడటానికి ఇది సరైన సమయమేనా?"
            voice = "Polly.Aditi" if language.lower() == "english" else "Polly.Vani"
            lang = "en-IN" if language.lower() == "english" else "te-IN"
            response.say(
                text,
                voice=voice,
                language=lang
            )

        gather = Gather(
            input="speech",
            action=f"{settings.WEBHOOK_BASE_URL}/api/webhook/voice/gather?session_id={session_id}",
            method="POST",
            language="te-IN" if language.lower() == "telugu" else "en-IN",
            speech_timeout="3",
            timeout=10
        )
        response.append(gather)

        # If no input, try again
        response.redirect(
            f"{settings.WEBHOOK_BASE_URL}/api/webhook/voice/no-input?session_id={session_id}",
            method="POST"
        )

        return str(response)

    def generate_response_twiml(self, session_id: str, audio_url: Optional[str] = None,
                                 text: str = "", language: str = "english",
                                 end_call: bool = False) -> str:
        """Generate TwiML for AI response with optional speech gathering."""
        response = VoiceResponse()

        if audio_url:
            response.play(audio_url)
        elif text:
            voice = "Polly.Aditi" if language.lower() == "english" else "Polly.Vani"
            lang = "en-IN" if language.lower() == "english" else "te-IN"
            response.say(text, voice=voice, language=lang)

        if end_call:
            response.hangup()
        else:
            gather = Gather(
                input="speech",
                action=f"{settings.WEBHOOK_BASE_URL}/api/webhook/voice/gather?session_id={session_id}",
                method="POST",
                language="te-IN" if language.lower() == "telugu" else "en-IN",
                speech_timeout="3",
                timeout=10
            )
            response.append(gather)

            response.redirect(
                f"{settings.WEBHOOK_BASE_URL}/api/webhook/voice/no-input?session_id={session_id}",
                method="POST"
            )

        return str(response)

    async def end_call(self, call_sid: str) -> bool:
        """End an active call."""
        if not self._init_client():
            return False

        try:
            self.client.calls(call_sid).update(status="completed")
            logger.info(f"Call ended: SID={call_sid}")
            return True
        except Exception as e:
            logger.error(f"Error ending call {call_sid}: {e}")
            return False


telephony_service = TelephonyService()
