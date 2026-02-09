from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
from enum import Enum
import uuid


class ConversationState(str, Enum):
    INTRO = "INTRO"
    FORM_CONFIRMATION = "FORM_CONFIRMATION"
    LANGUAGE_SELECTION = "LANGUAGE_SELECTION"
    SELF_INTRO = "SELF_INTRO"
    MOTIVATION = "MOTIVATION"
    BUSINESS_OVERVIEW = "BUSINESS_OVERVIEW"
    WHATSAPP_HANDOFF = "WHATSAPP_HANDOFF"
    CLOSING = "CLOSING"
    ENDED = "ENDED"


class CallStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_ANSWER = "no_answer"
    BUSY = "busy"


class LeadStatus(str, Enum):
    NEW = ""
    INTERESTED = "Interested"
    NOT_INTERESTED = "Not Interested"
    NO_ANSWER = "No Answer"
    BUSY = "Busy"
    CALLBACK = "Callback"
    WHATSAPP_SENT = "WhatsApp Sent"


class Lead(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    phone: str = ""
    status: str = ""
    call_attempts: int = 0
    language: str = ""
    last_called_at: Optional[str] = None
    whatsapp_sent: str = "No"
    row_number: int = 0  # Row in Google Sheet


class CallSession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lead_id: str
    lead_name: str = ""
    lead_phone: str = ""
    twilio_call_sid: str = ""
    conversation_state: str = ConversationState.INTRO.value
    language: str = ""
    interest_detected: bool = False
    call_status: str = CallStatus.PENDING.value
    transcript: List[dict] = []
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ended_at: Optional[str] = None
    whatsapp_sent: bool = False


class CallLog(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lead_id: str
    lead_name: str = ""
    lead_phone: str = ""
    call_sid: str = ""
    status: str = ""
    duration: int = 0
    conversation_state: str = ""
    interest_detected: bool = False
    whatsapp_sent: bool = False
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: str = ""


class SystemStatus(BaseModel):
    scheduler_running: bool = False
    last_scheduler_run: Optional[str] = None
    total_leads: int = 0
    leads_called: int = 0
    leads_interested: int = 0
    leads_not_interested: int = 0
    active_calls: int = 0
    twilio_configured: bool = False
    elevenlabs_configured: bool = False
    whatsapp_configured: bool = False
    sheets_configured: bool = False
    llm_configured: bool = False


# API request/response models
class ManualCallRequest(BaseModel):
    lead_id: Optional[str] = None
    phone: Optional[str] = None
    name: Optional[str] = None


class SchedulerControlRequest(BaseModel):
    action: str  # "start", "stop", "trigger"


class ConfigUpdateRequest(BaseModel):
    key: str
    value: str
