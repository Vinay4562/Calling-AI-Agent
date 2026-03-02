"""
AI Voice Agent - Conversation state machine powered by GPT-5.2.
Manages call flow through 8 states with interest detection.
"""
import logging
from typing import Tuple
# from emergentintegrations.llm.chat import LlmChat, UserMessage

from openai import AsyncOpenAI

class UserMessage:
    def __init__(self, text):
        self.text = text

class LlmChat:
    def __init__(self, api_key, session_id, system_message):
        self.client = AsyncOpenAI(api_key=api_key)
        self.session_id = session_id
        self.system_message = system_message
        self.model = "gpt-4-turbo-preview"  # Default to gpt-4
    
    def with_model(self, provider, model):
        # We'll use OpenAI provider, map model if needed
        if model == "gpt-5.2":
            self.model = "gpt-4-turbo-preview"
        else:
            self.model = model
        
    async def send_message(self, message):
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_message},
                    {"role": "user", "content": message.text}
                ],
                max_tokens=150,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error in LlmChat.send_message: {e}")
            return "I apologize, but I'm having trouble connecting right now. Let's talk again later."

from config import settings
from models.schemas import ConversationState

logger = logging.getLogger(__name__)

# Interest detection keywords
INTEREST_KEYWORDS_EN = [
    "okay", "ok", "sounds good", "send details", "whatsapp", "i will check",
    "tell me more", "interested", "sure", "yes", "please", "go ahead",
    "send it", "share", "video"
]

INTEREST_KEYWORDS_TE = [
    "sare", "ok", "pampandi", "video pampandi", "cheppandi", "avunu",
    "interest", "details pampandi", "whatsapp lo pampandi", "chustanu",
    "bagundi"
]

NOT_INTERESTED_KEYWORDS = [
    "not interested", "no", "busy", "don't call", "stop", "bye",
    "later", "nakku vaddu", "interest ledu", "busy ga unna", "vaddhu"
]

SYSTEM_PROMPT_TEMPLATE = """You are a polite outbound calling assistant for a work-from-home opportunity information service.

ROLE: Calm, slow, respectful, human-sounding voice caller.
CURRENT LANGUAGE: {language}
LEAD NAME: {lead_name}

STRICT RULES:
- NEVER promise guaranteed income
- NEVER mention fees, payments, or investment
- NEVER pressure or rush the user
- NEVER argue with the user
- If user says "not interested" or "busy", immediately say goodbye politely
- Do NOT sell anything on the call
- ONLY guide the conversation toward WhatsApp for details
- Keep responses SHORT (2-3 sentences max)
- Do NOT mix Telugu and English in the same response
- If language is Telugu, respond ONLY in Telugu
- If language is English, respond ONLY in English

CURRENT CONVERSATION STATE: {state}

STATE INSTRUCTIONS:
- INTRO: Greet the user by name. Confirm their name. Ask if it's a good time to talk.
- FORM_CONFIRMATION: Confirm they recently filled a form about work-from-home / part-time opportunities.
- LANGUAGE_SELECTION: Ask if they prefer Telugu or English for the conversation.
- SELF_INTRO: Politely ask the user to give a brief introduction about themselves.
- MOTIVATION: Ask why they filled the form / what they're looking for.
- BUSINESS_OVERVIEW: Give a HIGH-LEVEL 30-second overview. Say it's a flexible work-from-home opportunity. Do NOT go into details.
- WHATSAPP_HANDOFF: Say you'll share a short 5-6 minute introduction video on WhatsApp. Ask them to send "Hi" on WhatsApp.
- CLOSING: Thank the user warmly. Wish them well. Say goodbye.

Respond naturally as if you are on a phone call. Keep it conversational and warm."""


def detect_interest(text: str) -> bool:
    """Check if user shows interest based on keywords."""
    text_lower = text.lower().strip()
    all_keywords = INTEREST_KEYWORDS_EN + INTEREST_KEYWORDS_TE
    for keyword in all_keywords:
        if keyword in text_lower:
            return True
    return False


def detect_not_interested(text: str) -> bool:
    """Check if user is not interested."""
    text_lower = text.lower().strip()
    for keyword in NOT_INTERESTED_KEYWORDS:
        if keyword in text_lower:
            return True
    return False


def get_next_state(current_state: str, user_input: str, interest: bool, not_interested: bool) -> str:
    """Determine next conversation state based on current state and user input."""
    if not_interested:
        return ConversationState.CLOSING.value

    state_transitions = {
        ConversationState.INTRO.value: ConversationState.FORM_CONFIRMATION.value,
        ConversationState.FORM_CONFIRMATION.value: ConversationState.LANGUAGE_SELECTION.value,
        ConversationState.LANGUAGE_SELECTION.value: ConversationState.SELF_INTRO.value,
        ConversationState.SELF_INTRO.value: ConversationState.MOTIVATION.value,
        ConversationState.MOTIVATION.value: ConversationState.BUSINESS_OVERVIEW.value,
        ConversationState.BUSINESS_OVERVIEW.value: ConversationState.WHATSAPP_HANDOFF.value,
        ConversationState.WHATSAPP_HANDOFF.value: ConversationState.CLOSING.value,
        ConversationState.CLOSING.value: ConversationState.ENDED.value,
    }

    return state_transitions.get(current_state, ConversationState.CLOSING.value)


def detect_language_choice(text: str) -> str:
    """Detect which language the user chose."""
    text_lower = text.lower().strip()
    telugu_indicators = ["telugu", "తెలుగు", "telugu lo", "telugulo"]
    english_indicators = ["english", "ఇంగ్లీష్", "english lo"]

    for indicator in telugu_indicators:
        if indicator in text_lower:
            return "telugu"
    for indicator in english_indicators:
        if indicator in text_lower:
            return "english"
    # Default to English if unclear
    return "english"


async def generate_ai_response(
    session_id: str,
    lead_name: str,
    language: str,
    conversation_state: str,
    user_input: str
) -> str:
    """Generate AI response using GPT-5.2."""
    if not settings.is_llm_configured():
        logger.warning("LLM not configured. Returning fallback response.")
        return _get_fallback_response(conversation_state, language, lead_name)

    try:
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            language=language or "English",
            lead_name=lead_name,
            state=conversation_state
        )

        chat = LlmChat(
            api_key=settings.LLM_API_KEY,
            session_id=session_id,
            system_message=system_prompt
        )
        chat.with_model("openai", "gpt-5.2")

        message = UserMessage(text=user_input if user_input else "Start the conversation.")
        response = await chat.send_message(message)
        logger.info(f"AI response for state {conversation_state}: {response[:100]}...")
        return response
    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        return _get_fallback_response(conversation_state, language, lead_name)


def _get_fallback_response(state: str, language: str, name: str) -> str:
    """Fallback responses when LLM is unavailable."""
    responses_en = {
        ConversationState.INTRO.value: f"Hello {name}! This is a quick call regarding an opportunity you showed interest in. Is this a good time to talk?",
        ConversationState.FORM_CONFIRMATION.value: "We noticed you recently filled a form about work-from-home opportunities. Is that correct?",
        ConversationState.LANGUAGE_SELECTION.value: "Would you prefer to continue this conversation in Telugu or English?",
        ConversationState.SELF_INTRO.value: "That's great! Could you tell me a little about yourself?",
        ConversationState.MOTIVATION.value: "What made you interested in exploring work-from-home opportunities?",
        ConversationState.BUSINESS_OVERVIEW.value: "We have a flexible work-from-home opportunity that many people across India are benefiting from. It requires just a few hours daily and can be done from anywhere.",
        ConversationState.WHATSAPP_HANDOFF.value: "I'd love to share a short 5-6 minute introduction video with you on WhatsApp. Could you please send 'Hi' to our WhatsApp number so I can share the details?",
        ConversationState.CLOSING.value: "Thank you so much for your time! Have a wonderful day!",
    }

    responses_te = {
        ConversationState.INTRO.value: f"నమస్కారం {name}! మీరు ఆసక్తి చూపిన ఒక అవకాశం గురించి కాల్ చేస్తున్నాను. ఇప్పుడు మాట్లాడటానికి సమయం ఉందా?",
        ConversationState.FORM_CONFIRMATION.value: "మీరు ఇటీవల వర్క్ ఫ్రమ్ హోమ్ అవకాశాల గురించి ఒక ఫారమ్ నింపారు. అది కరెక్టేనా?",
        ConversationState.LANGUAGE_SELECTION.value: "మీరు తెలుగులో లేదా ఇంగ్లీషులో మాట్లాడాలనుకుంటున్నారా?",
        ConversationState.SELF_INTRO.value: "బాగుంది! మీ గురించి కొంచెం చెప్పగలరా?",
        ConversationState.MOTIVATION.value: "వర్క్ ఫ్రమ్ హోమ్ అవకాశాల గురించి మీకు ఆసక్తి ఎందుకు కలిగింది?",
        ConversationState.BUSINESS_OVERVIEW.value: "మా దగ్గర ఒక ఫ్లెక్సిబుల్ వర్క్ ఫ్రమ్ హోమ్ అవకాశం ఉంది. దీనికి రోజుకు కొన్ని గంటలు మాత్రమే అవసరం మరియు ఎక్కడి నుండైనా చేయవచ్చు.",
        ConversationState.WHATSAPP_HANDOFF.value: "మీకు వాట్సాప్ లో 5-6 నిమిషాల పరిచయ వీడియో పంపాలనుకుంటున్నాను. దయచేసి మా వాట్సాప్ నంబర్ కి 'Hi' పంపగలరా?",
        ConversationState.CLOSING.value: "మీ సమయానికి చాలా ధన్యవాదాలు! మంచి రోజు గడపండి!",
    }

    responses = responses_te if language == "telugu" else responses_en
    return responses.get(state, "Thank you for your time.")
