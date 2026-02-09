"""
Outbound AI Calling System with WhatsApp Follow-up
Main FastAPI application with webhook handlers, API endpoints, and scheduler.
"""
import sys
import os
import base64
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import FastAPI, APIRouter, HTTPException, Request, Form, Response
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pydantic import BaseModel
import uuid

# Setup path
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))
load_dotenv(ROOT_DIR / '.env')

from config import settings
from models.schemas import (
    Lead, CallSession, CallLog, SystemStatus,
    ConversationState, CallStatus, LeadStatus,
    ManualCallRequest, SchedulerControlRequest
)
from services.sheets_service import sheets_service
from services.telephony_service import telephony_service
from services.ai_agent import (
    generate_ai_response, detect_interest, detect_not_interested,
    get_next_state, detect_language_choice
)
from services.tts_service import tts_service
from services.whatsapp_service import whatsapp_service
from services.scheduler_service import scheduler_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', '')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'test_database')]

# FastAPI app
app = FastAPI(title="Outbound AI Calling System", version="1.0.0")
api_router = APIRouter(prefix="/api")

# In-memory audio cache for serving TTS audio to Twilio
audio_cache = {}


# ==================== CORE CALLING LOGIC ====================

async def process_next_lead():
    """Process the next eligible lead - called by scheduler."""
    logger.info("Processing next eligible lead...")

    # Try Google Sheets first
    lead = sheets_service.get_next_eligible_lead()

    # Fallback to MongoDB leads
    if lead is None:
        lead_doc = await db.leads.find_one(
            {"status": "", "call_attempts": {"$lt": 2}},
            {"_id": 0},
            sort=[("call_attempts", 1)]
        )
        if lead_doc:
            lead = Lead(**lead_doc)

    if lead is None:
        logger.info("No eligible leads found")
        return

    logger.info(f"Starting call for lead: {lead.name} ({lead.phone})")
    await initiate_call_for_lead(lead)


async def initiate_call_for_lead(lead: Lead):
    """Initiate a call for a specific lead."""
    session_id = str(uuid.uuid4())

    # Create call session in MongoDB
    session = CallSession(
        id=session_id,
        lead_id=lead.id,
        lead_name=lead.name,
        lead_phone=lead.phone,
        conversation_state=ConversationState.INTRO.value,
        call_status=CallStatus.PENDING.value
    )

    session_dict = session.model_dump()
    await db.call_sessions.insert_one(session_dict)

    # Mark scheduler as having a call in progress
    scheduler_service.call_in_progress = True

    # Generate initial greeting
    greeting = await generate_ai_response(
        session_id=session_id,
        lead_name=lead.name,
        language="english",
        conversation_state=ConversationState.INTRO.value,
        user_input=""
    )

    # Generate TTS audio for greeting
    tts_result = await tts_service.generate_speech(greeting, "english")
    if tts_result:
        audio_cache[tts_result["audio_id"]] = tts_result["audio_data"]

    # Initiate the Twilio call
    call_sid = await telephony_service.initiate_call(lead.phone, session_id)

    if call_sid:
        await db.call_sessions.update_one(
            {"id": session_id},
            {"$set": {
                "twilio_call_sid": call_sid,
                "call_status": CallStatus.IN_PROGRESS.value
            }}
        )
        logger.info(f"Call initiated: session={session_id}, sid={call_sid}")
    else:
        await _handle_call_failure(session_id, lead)
        logger.error(f"Failed to initiate call for lead {lead.id}")


async def _handle_call_failure(session_id: str, lead: Lead):
    """Handle call initiation failure."""
    scheduler_service.call_in_progress = False
    new_attempts = lead.call_attempts + 1
    status = "Failed" if new_attempts >= 2 else ""

    await db.call_sessions.update_one(
        {"id": session_id},
        {"$set": {"call_status": CallStatus.FAILED.value,
                  "ended_at": datetime.now(timezone.utc).isoformat()}}
    )

    # Update lead in MongoDB
    await db.leads.update_one(
        {"id": lead.id},
        {"$set": {"status": status, "call_attempts": new_attempts,
                  "last_called_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )

    # Update Google Sheets
    if lead.row_number > 0:
        sheets_service.update_lead_status(lead.row_number, status, new_attempts)

    # Log the call
    await db.call_logs.insert_one({
        "id": str(uuid.uuid4()),
        "lead_id": lead.id,
        "lead_name": lead.name,
        "lead_phone": lead.phone,
        "call_sid": "",
        "status": "failed",
        "duration": 0,
        "conversation_state": ConversationState.INTRO.value,
        "interest_detected": False,
        "whatsapp_sent": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "notes": "Call initiation failed"
    })


async def _finalize_call(session_id: str):
    """Finalize a call session - update all statuses."""
    session_doc = await db.call_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session_doc:
        return

    session = CallSession(**session_doc)
    scheduler_service.call_in_progress = False

    # Determine final lead status
    if session.interest_detected:
        lead_status = LeadStatus.INTERESTED.value
    elif session.conversation_state == ConversationState.CLOSING.value:
        lead_status = LeadStatus.NOT_INTERESTED.value
    else:
        lead_status = LeadStatus.NO_ANSWER.value

    # Send WhatsApp if interested
    whatsapp_sent = False
    if session.interest_detected:
        whatsapp_sent = await whatsapp_service.send_followup(
            session.lead_phone, session.lead_name, session.language or "english"
        )
        if whatsapp_sent:
            lead_status = LeadStatus.WHATSAPP_SENT.value
            logger.info(f"WhatsApp follow-up sent to {session.lead_phone}")

    # Update session
    await db.call_sessions.update_one(
        {"id": session_id},
        {"$set": {
            "call_status": CallStatus.COMPLETED.value,
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "whatsapp_sent": whatsapp_sent
        }}
    )

    # Update lead in MongoDB
    lead_doc = await db.leads.find_one({"id": session.lead_id}, {"_id": 0})
    new_attempts = (lead_doc.get("call_attempts", 0) if lead_doc else 0) + 1

    await db.leads.update_one(
        {"id": session.lead_id},
        {"$set": {
            "status": lead_status,
            "call_attempts": new_attempts,
            "language": session.language,
            "last_called_at": datetime.now(timezone.utc).isoformat(),
            "whatsapp_sent": "Yes" if whatsapp_sent else "No"
        }},
        upsert=True
    )

    # Update Google Sheets
    lead = await db.leads.find_one({"id": session.lead_id}, {"_id": 0})
    row = lead.get("row_number", 0) if lead else 0
    if row > 0:
        sheets_service.update_lead_status(
            row, lead_status, new_attempts,
            session.language, "Yes" if whatsapp_sent else "No"
        )

    # Create call log
    await db.call_logs.insert_one({
        "id": str(uuid.uuid4()),
        "lead_id": session.lead_id,
        "lead_name": session.lead_name,
        "lead_phone": session.lead_phone,
        "call_sid": session.twilio_call_sid,
        "status": lead_status,
        "duration": 0,
        "conversation_state": session.conversation_state,
        "interest_detected": session.interest_detected,
        "whatsapp_sent": whatsapp_sent,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "notes": f"Call completed. State: {session.conversation_state}"
    })

    logger.info(f"Call finalized: session={session_id}, status={lead_status}, whatsapp={whatsapp_sent}")


# ==================== TWILIO WEBHOOKS ====================

@api_router.post("/webhook/voice/answer")
async def voice_answer_webhook(request: Request, session_id: str = ""):
    """Twilio calls this when the outbound call is answered."""
    logger.info(f"Call answered: session={session_id}")

    session_doc = await db.call_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session_doc:
        response = telephony_service.generate_response_twiml(
            session_id, text="Sorry, there was an error. Goodbye.", end_call=True
        )
        return Response(content=response, media_type="application/xml")

    session = CallSession(**session_doc)

    # Generate greeting
    greeting = await generate_ai_response(
        session_id=session_id,
        lead_name=session.lead_name,
        language="english",
        conversation_state=ConversationState.INTRO.value,
        user_input=""
    )

    # Add to transcript
    await db.call_sessions.update_one(
        {"id": session_id},
        {"$push": {"transcript": {"role": "agent", "text": greeting, "state": ConversationState.INTRO.value}}}
    )

    # Generate TTS and serve
    tts_result = await tts_service.generate_speech(greeting, "english")
    audio_url = None
    if tts_result:
        audio_cache[tts_result["audio_id"]] = tts_result["audio_data"]
        audio_url = f"{settings.WEBHOOK_BASE_URL}/api/audio/{tts_result['audio_id']}"

    twiml = telephony_service.generate_greeting_twiml(session_id, audio_url)
    return Response(content=twiml, media_type="application/xml")


@api_router.post("/webhook/voice/gather")
async def voice_gather_webhook(request: Request, session_id: str = ""):
    """Twilio calls this when speech is gathered from the user."""
    form_data = await request.form()
    speech_result = form_data.get("SpeechResult", "")
    confidence = form_data.get("Confidence", "0")

    logger.info(f"Speech gathered: session={session_id}, text='{speech_result}', confidence={confidence}")

    session_doc = await db.call_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session_doc:
        twiml = telephony_service.generate_response_twiml(
            session_id, text="Goodbye.", end_call=True
        )
        return Response(content=twiml, media_type="application/xml")

    session = CallSession(**session_doc)
    current_state = session.conversation_state
    language = session.language or "english"

    # Add user speech to transcript
    await db.call_sessions.update_one(
        {"id": session_id},
        {"$push": {"transcript": {"role": "user", "text": speech_result, "state": current_state}}}
    )

    # Language detection in LANGUAGE_SELECTION state
    if current_state == ConversationState.LANGUAGE_SELECTION.value:
        language = detect_language_choice(speech_result)
        await db.call_sessions.update_one(
            {"id": session_id},
            {"$set": {"language": language}}
        )

    # Interest detection
    interest = detect_interest(speech_result)
    not_interested = detect_not_interested(speech_result)

    if interest:
        await db.call_sessions.update_one(
            {"id": session_id},
            {"$set": {"interest_detected": True}}
        )
        logger.info(f"Interest detected: session={session_id}")

    if not_interested:
        logger.info(f"Not interested detected: session={session_id}")

    # Determine next state
    next_state = get_next_state(current_state, speech_result, interest, not_interested)
    await db.call_sessions.update_one(
        {"id": session_id},
        {"$set": {"conversation_state": next_state}}
    )

    # Generate AI response for the next state
    ai_response = await generate_ai_response(
        session_id=session_id,
        lead_name=session.lead_name,
        language=language,
        conversation_state=next_state,
        user_input=speech_result
    )

    # Add AI response to transcript
    await db.call_sessions.update_one(
        {"id": session_id},
        {"$push": {"transcript": {"role": "agent", "text": ai_response, "state": next_state}}}
    )

    # Check if we should end the call
    end_call = next_state in [ConversationState.ENDED.value, ConversationState.CLOSING.value]

    # If CLOSING state, we'll say the closing message then end
    if next_state == ConversationState.CLOSING.value:
        # After closing, finalize
        end_call = True

    # Generate TTS
    tts_result = await tts_service.generate_speech(ai_response, language)
    audio_url = None
    if tts_result:
        audio_cache[tts_result["audio_id"]] = tts_result["audio_data"]
        audio_url = f"{settings.WEBHOOK_BASE_URL}/api/audio/{tts_result['audio_id']}"

    twiml = telephony_service.generate_response_twiml(
        session_id, audio_url=audio_url, text=ai_response,
        language=language, end_call=end_call
    )

    # If ending, finalize the call
    if end_call:
        await _finalize_call(session_id)

    return Response(content=twiml, media_type="application/xml")


@api_router.post("/webhook/voice/status")
async def voice_status_webhook(request: Request, session_id: str = ""):
    """Twilio call status callback."""
    form_data = await request.form()
    call_status = form_data.get("CallStatus", "")
    call_sid = form_data.get("CallSid", "")
    duration = form_data.get("CallDuration", "0")

    logger.info(f"Call status: session={session_id}, status={call_status}, sid={call_sid}")

    if call_status in ["completed", "busy", "no-answer", "failed", "canceled"]:
        session_doc = await db.call_sessions.find_one({"id": session_id}, {"_id": 0})
        if session_doc and session_doc.get("call_status") != CallStatus.COMPLETED.value:
            await _finalize_call(session_id)

    return JSONResponse({"status": "ok"})


@api_router.post("/webhook/voice/no-input")
async def voice_no_input_webhook(request: Request, session_id: str = ""):
    """Handle when user doesn't respond."""
    logger.info(f"No input from user: session={session_id}")

    session_doc = await db.call_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session_doc:
        twiml = telephony_service.generate_response_twiml(
            session_id, text="Goodbye.", end_call=True
        )
        return Response(content=twiml, media_type="application/xml")

    prompt_text = "I didn't catch that. Could you please repeat?"
    tts_result = await tts_service.generate_speech(prompt_text, session_doc.get("language", "english"))
    audio_url = None
    if tts_result:
        audio_cache[tts_result["audio_id"]] = tts_result["audio_data"]
        audio_url = f"{settings.WEBHOOK_BASE_URL}/api/audio/{tts_result['audio_id']}"

    twiml = telephony_service.generate_response_twiml(
        session_id, audio_url=audio_url, text=prompt_text,
        language=session_doc.get("language", "english")
    )
    return Response(content=twiml, media_type="application/xml")


# ==================== AUDIO SERVING ====================

@api_router.get("/audio/{audio_id}")
async def serve_audio(audio_id: str):
    """Serve TTS audio for Twilio to play."""
    audio_data = audio_cache.get(audio_id)
    if not audio_data:
        raise HTTPException(status_code=404, detail="Audio not found")

    return Response(content=audio_data, media_type="audio/mpeg")


# ==================== API ENDPOINTS ====================

@api_router.get("/")
async def root():
    return {"message": "Outbound AI Calling System v1.0", "status": "running"}


@api_router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "twilio": settings.is_twilio_configured(),
            "elevenlabs": settings.is_elevenlabs_configured(),
            "whatsapp": settings.is_whatsapp_configured(),
            "google_sheets": settings.is_sheets_configured(),
            "llm": settings.is_llm_configured()
        }
    }


@api_router.get("/system/status")
async def get_system_status():
    """Get comprehensive system status."""
    total_leads = await db.leads.count_documents({})
    interested = await db.leads.count_documents({"status": {"$in": ["Interested", "WhatsApp Sent"]}})
    not_interested = await db.leads.count_documents({"status": "Not Interested"})
    called = await db.leads.count_documents({"call_attempts": {"$gt": 0}})
    active_calls = await db.call_sessions.count_documents({"call_status": "in_progress"})

    scheduler_status = scheduler_service.get_status()

    return SystemStatus(
        scheduler_running=scheduler_status["is_running"],
        last_scheduler_run=scheduler_status["last_run_at"],
        total_leads=total_leads,
        leads_called=called,
        leads_interested=interested,
        leads_not_interested=not_interested,
        active_calls=active_calls,
        twilio_configured=settings.is_twilio_configured(),
        elevenlabs_configured=settings.is_elevenlabs_configured(),
        whatsapp_configured=settings.is_whatsapp_configured(),
        sheets_configured=settings.is_sheets_configured(),
        llm_configured=settings.is_llm_configured()
    ).model_dump()


# ==================== LEAD MANAGEMENT ====================

@api_router.get("/leads")
async def get_leads():
    """Get all leads from MongoDB."""
    leads = await db.leads.find({}, {"_id": 0}).to_list(1000)
    return leads


@api_router.post("/leads")
async def create_lead(lead: Lead):
    """Create a new lead manually."""
    lead_dict = lead.model_dump()
    await db.leads.insert_one(lead_dict)
    return {k: v for k, v in lead_dict.items() if k != "_id"}


@api_router.post("/leads/sync-sheets")
async def sync_leads_from_sheets():
    """Sync leads from Google Sheets to MongoDB."""
    leads = sheets_service.get_all_leads()
    if not leads:
        return {"message": "No leads found or Sheets not configured", "synced": 0}

    synced = 0
    for lead in leads:
        lead_dict = lead.model_dump()
        await db.leads.update_one(
            {"id": lead.id},
            {"$set": lead_dict},
            upsert=True
        )
        synced += 1

    return {"message": f"Synced {synced} leads from Google Sheets", "synced": synced}


@api_router.post("/leads/bulk")
async def create_leads_bulk(leads: List[Lead]):
    """Create multiple leads at once."""
    created = 0
    for lead in leads:
        lead_dict = lead.model_dump()
        await db.leads.update_one(
            {"id": lead.id},
            {"$set": lead_dict},
            upsert=True
        )
        created += 1
    return {"message": f"Created {created} leads", "created": created}


# ==================== CALL MANAGEMENT ====================

@api_router.post("/calls/initiate")
async def initiate_manual_call(req: ManualCallRequest):
    """Manually initiate a call to a specific lead or phone number."""
    if req.lead_id:
        lead_doc = await db.leads.find_one({"id": req.lead_id}, {"_id": 0})
        if not lead_doc:
            raise HTTPException(status_code=404, detail="Lead not found")
        lead = Lead(**lead_doc)
    elif req.phone:
        lead = Lead(
            id=str(uuid.uuid4()),
            name=req.name or "Unknown",
            phone=req.phone
        )
        await db.leads.insert_one(lead.model_dump())
    else:
        raise HTTPException(status_code=400, detail="Provide lead_id or phone number")

    await initiate_call_for_lead(lead)
    return {"message": f"Call initiated for {lead.name}", "phone": lead.phone}


@api_router.get("/calls/active")
async def get_active_calls():
    """Get currently active call sessions."""
    sessions = await db.call_sessions.find(
        {"call_status": "in_progress"},
        {"_id": 0}
    ).to_list(100)
    return sessions


@api_router.get("/calls/history")
async def get_call_history(limit: int = 50):
    """Get call history logs."""
    logs = await db.call_logs.find(
        {},
        {"_id": 0}
    ).sort("timestamp", -1).to_list(limit)
    return logs


@api_router.get("/calls/sessions")
async def get_call_sessions(limit: int = 50):
    """Get call sessions with full details."""
    sessions = await db.call_sessions.find(
        {},
        {"_id": 0}
    ).sort("started_at", -1).to_list(limit)
    return sessions


@api_router.get("/calls/session/{session_id}")
async def get_call_session(session_id: str):
    """Get a specific call session with transcript."""
    session = await db.call_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# ==================== SCHEDULER CONTROL ====================

@api_router.post("/scheduler/control")
async def control_scheduler(req: SchedulerControlRequest):
    """Control the scheduler: start, stop, or trigger manually."""
    if req.action == "start":
        scheduler_service.start()
        return {"message": "Scheduler started"}
    elif req.action == "stop":
        scheduler_service.stop()
        return {"message": "Scheduler stopped"}
    elif req.action == "trigger":
        await scheduler_service.trigger_now()
        return {"message": "Scheduler triggered manually"}
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use: start, stop, trigger")


@api_router.get("/scheduler/status")
async def get_scheduler_status():
    """Get scheduler status."""
    return scheduler_service.get_status()


# ==================== CONFIGURATION ====================

@api_router.get("/config/status")
async def get_config_status():
    """Get which integrations are configured."""
    return {
        "twilio": {
            "configured": settings.is_twilio_configured(),
            "phone_number": settings.TWILIO_PHONE_NUMBER[:6] + "****" if settings.TWILIO_PHONE_NUMBER else "Not set"
        },
        "elevenlabs": {
            "configured": settings.is_elevenlabs_configured()
        },
        "whatsapp": {
            "configured": settings.is_whatsapp_configured(),
            "number": settings.TWILIO_WHATSAPP_NUMBER[:6] + "****" if settings.TWILIO_WHATSAPP_NUMBER else "Not set"
        },
        "google_sheets": {
            "configured": settings.is_sheets_configured(),
            "sheet_id": settings.GOOGLE_SHEET_ID[:10] + "..." if settings.GOOGLE_SHEET_ID else "Not set"
        },
        "llm": {
            "configured": settings.is_llm_configured(),
            "model": "gpt-5.2"
        },
        "webhook_base_url": settings.WEBHOOK_BASE_URL or "Not set"
    }


# ==================== STATS ====================

@api_router.get("/stats/dashboard")
async def get_dashboard_stats():
    """Get dashboard statistics."""
    total = await db.leads.count_documents({})
    new_leads = await db.leads.count_documents({"status": ""})
    interested = await db.leads.count_documents({"status": {"$in": ["Interested", "WhatsApp Sent"]}})
    not_interested = await db.leads.count_documents({"status": "Not Interested"})
    no_answer = await db.leads.count_documents({"status": "No Answer"})
    whatsapp_sent = await db.leads.count_documents({"whatsapp_sent": "Yes"})
    total_calls = await db.call_logs.count_documents({})
    active_calls = await db.call_sessions.count_documents({"call_status": "in_progress"})

    # Recent call logs
    recent_logs = await db.call_logs.find(
        {}, {"_id": 0}
    ).sort("timestamp", -1).to_list(10)

    scheduler_status = scheduler_service.get_status()

    return {
        "leads": {
            "total": total,
            "new": new_leads,
            "interested": interested,
            "not_interested": not_interested,
            "no_answer": no_answer,
            "whatsapp_sent": whatsapp_sent
        },
        "calls": {
            "total": total_calls,
            "active": active_calls
        },
        "scheduler": scheduler_status,
        "recent_logs": recent_logs,
        "integrations": {
            "twilio": settings.is_twilio_configured(),
            "elevenlabs": settings.is_elevenlabs_configured(),
            "whatsapp": settings.is_whatsapp_configured(),
            "sheets": settings.is_sheets_configured(),
            "llm": settings.is_llm_configured()
        }
    }


# ==================== APP SETUP ====================

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=settings.CORS_ORIGINS.split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    """Initialize services on startup."""
    logger.info("Starting Outbound AI Calling System...")

    # Configure scheduler
    scheduler_service.configure(db, process_next_lead)

    # Create MongoDB indexes
    await db.leads.create_index("id", unique=True)
    await db.leads.create_index("status")
    await db.leads.create_index("phone")
    await db.call_sessions.create_index("id", unique=True)
    await db.call_sessions.create_index("lead_id")
    await db.call_sessions.create_index("twilio_call_sid")
    await db.call_logs.create_index("lead_id")
    await db.call_logs.create_index("timestamp")

    logger.info("System initialized. Use /api/scheduler/control to start the scheduler.")


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    scheduler_service.stop()
    client.close()
    logger.info("System shut down.")
