"""
WhatsApp Follow-up Service - Sends WhatsApp messages via Twilio.
Only sends if interest is detected during the call.
"""
import logging
from config import settings

logger = logging.getLogger(__name__)


WHATSAPP_MESSAGES = {
    "english": (
        "Hi {name}! Thank you for speaking with us today.\n\n"
        "As discussed, here's a short 5-6 minute introduction video that explains "
        "how our work-from-home opportunity works.\n\n"
        "Take your time to watch it, and feel free to reply here if you have any questions.\n\n"
        "Have a great day!"
    ),
    "telugu": (
        "నమస్కారం {name}! ఈ రోజు మాతో మాట్లాడినందుకు ధన్యవాదాలు.\n\n"
        "మనం మాట్లాడినట్లుగా, మా వర్క్ ఫ్రమ్ హోమ్ అవకాశం ఎలా పనిచేస్తుందో వివరించే "
        "5-6 నిమిషాల పరిచయ వీడియో ఇక్కడ ఉంది.\n\n"
        "దయచేసి మీ సమయంలో చూడండి, ఏవైనా ప్రశ్నలు ఉంటే ఇక్కడ రిప్లై చేయండి.\n\n"
        "మంచి రోజు గడపండి!"
    )
}


class WhatsAppService:
    def __init__(self):
        self.client = None
        self._initialized = False

    def _init_client(self):
        """Initialize Twilio client for WhatsApp."""
        if self._initialized:
            return True

        if not settings.is_whatsapp_configured():
            logger.warning("WhatsApp (Twilio) not configured.")
            return False

        try:
            from twilio.rest import Client
            self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            self._initialized = True
            logger.info("Twilio WhatsApp client initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Twilio WhatsApp: {e}")
            return False

    async def send_followup(self, phone: str, name: str, language: str = "english") -> bool:
        """
        Send WhatsApp follow-up message.
        Only call this if interest was detected during the call.
        """
        if not self._init_client():
            logger.warning("WhatsApp not configured. Skipping follow-up.")
            return False

        try:
            # Ensure phone has country code
            if not phone.startswith("+"):
                phone = f"+91{phone}"

            template = WHATSAPP_MESSAGES.get(language.lower(), WHATSAPP_MESSAGES["english"])
            message_body = template.format(name=name)

            from_number = f"whatsapp:{settings.TWILIO_WHATSAPP_NUMBER}"
            to_number = f"whatsapp:{phone}"

            logger.info(f"Attempting to send WhatsApp from {from_number} to {to_number}")
            message = self.client.messages.create(
                body=message_body,
                from_=from_number,
                to=to_number
            )

            logger.info(f"WhatsApp message status: {message.status}, SID: {message.sid}")
            return True
        except Exception as e:
            logger.error(f"Error sending WhatsApp to {phone}: {e}")
            return False


whatsapp_service = WhatsAppService()
