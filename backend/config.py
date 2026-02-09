import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')


class Settings:
    # MongoDB
    MONGO_URL: str = os.environ.get('MONGO_URL', '')
    DB_NAME: str = os.environ.get('DB_NAME', '')

    # Twilio
    TWILIO_ACCOUNT_SID: str = os.environ.get('TWILIO_ACCOUNT_SID', '')
    TWILIO_AUTH_TOKEN: str = os.environ.get('TWILIO_AUTH_TOKEN', '')
    TWILIO_PHONE_NUMBER: str = os.environ.get('TWILIO_PHONE_NUMBER', '')
    TWILIO_WHATSAPP_NUMBER: str = os.environ.get('TWILIO_WHATSAPP_NUMBER', '')

    # ElevenLabs
    ELEVENLABS_API_KEY: str = os.environ.get('ELEVENLABS_API_KEY', '')
    ELEVENLABS_VOICE_ID: str = os.environ.get('ELEVENLABS_VOICE_ID', '')

    # OpenAI / Emergent LLM
    EMERGENT_LLM_KEY: str = os.environ.get('EMERGENT_LLM_KEY', '')

    # Google Sheets
    GOOGLE_SHEET_ID: str = os.environ.get('GOOGLE_SHEET_ID', '')
    GOOGLE_SERVICE_ACCOUNT_JSON: str = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON', '')

    # Webhook
    WEBHOOK_BASE_URL: str = os.environ.get('WEBHOOK_BASE_URL', '')

    # CORS
    CORS_ORIGINS: str = os.environ.get('CORS_ORIGINS', '*')

    # Scheduler
    SCHEDULER_INTERVAL_MINUTES: int = int(os.environ.get('SCHEDULER_INTERVAL_MINUTES', '10'))

    def is_twilio_configured(self) -> bool:
        return bool(self.TWILIO_ACCOUNT_SID and self.TWILIO_AUTH_TOKEN and self.TWILIO_PHONE_NUMBER)

    def is_elevenlabs_configured(self) -> bool:
        return bool(self.ELEVENLABS_API_KEY)

    def is_whatsapp_configured(self) -> bool:
        return bool(self.TWILIO_WHATSAPP_NUMBER and self.is_twilio_configured())

    def is_sheets_configured(self) -> bool:
        return bool(self.GOOGLE_SHEET_ID and self.GOOGLE_SERVICE_ACCOUNT_JSON)

    def is_llm_configured(self) -> bool:
        return bool(self.EMERGENT_LLM_KEY)


settings = Settings()
