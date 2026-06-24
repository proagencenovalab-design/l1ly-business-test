import json
import os
import random
import re
from typing import Any, Dict, List, Optional

from openai import OpenAI

BOT_VERSION = "v10.0-stable"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini").strip()

FANVUE_LINK = os.getenv("FANVUE_LINK", "").strip()
DIRECT_PRODUCT_LINK = os.getenv("DIRECT_PRODUCT_LINK", "").strip()
WHOP_STARTER_LINK = os.getenv("WHOP_STARTER_LINK", "").strip()
WHOP_PREMIUM_LINK = os.getenv("WHOP_PREMIUM_LINK", "").strip()
WHOP_VIP_LINK = os.getenv("WHOP_VIP_LINK", "").strip()

_openai_client: Optional[OpenAI] = None


def _norm(text: str) -> str:
    return (text or "").replace("’", "'").strip().lower()


def _whole_match(text: str, phrase: str) -> bool:
    text = _norm(text)
    phrase = _norm(phrase)
    if not phrase:
        return False
    return re.search(r"(?<!\\w)" + re.escape(phrase) + r"(?!\\w)", text) is not None


def contains_any(text: str, phrases: List[str]) -> bool:
    return any(_whole_match(text, phrase) for phrase in phrases)


BLOCKED_WORDS = [
    "minor", "under 18", "underage", "child", "teen", "15 years old",
    "16 years old", "17 years old", "mineur", "moins de 18", "enfant",
    "ado", "rape", "force", "blackmail", "threat", "incest",
    "viol", "forcer", "chantage", "menace", "inceste",
]

SPICY_WORDS = [
    "nude", "nudes", "naked", "boobs", "tits", "ass", "pussy",
    "show me", "send me", "hot pics", "sexy pics", "your body",
    "nue", "nu", "seins",
]

BUY_WORDS = [
    "price", "how much", "cost", "buy", "pay", "pack", "vip", "premium",
    "private content", "private pics", "private video", "link", "menu",
    "prix", "tarif", "combien", "payer", "acheter", "contenu privé",
]

TIMEWASTER_WORDS = [
    "free", "for free", "send first", "show me first", "preview first",
    "no money", "i'll pay later", "i will pay later", "gratuit",
    "envoie d'abord", "montre avant", "je paie après",
]

REPAIR_WORDS = [
    "what u mean", "what you mean", "what do you mean", "wdym", "huh",
    "i don't understand", "i dont understand", "that makes no sense",
    "what are you saying", "bro wtf", "wtf", "you're creepy",
    "you are creepy", "u are creepy", "confusing", "confused",
    "why aren't you answering", "why arent you answering",
    "answer my question", "you didn't answer", "you didnt answer",
]


def detect_language_switch(message: str) -> Optional[str]:
    msg = _norm(message)
    french = [
        "continuer en français", "continuer en francais", "parler français",
        "parler francais", "on peut parler français", "on peut parler francais",
        "can we speak french", "speak french please",
    ]
    english = [
        "continue in english", "speak english", "can we speak english",
        "english please",
    ]
    if any(x in msg for x in french):
        return "french"
    if any(x in msg for x in english):
        return "english"
    return None


def detect_language(message: str, preferred_language: str = "") -> str:
    explicit = detect_language_switch(message)
    if explicit:
        return explicit
    if preferred_language in {"english", "french"}:
        return preferred_language

    msg = _norm(message)
    fr_markers = [
        "salut", "bonjour", "bonsoir", "coucou", "ça va", "français",
        "francais", "je suis", "j'ai", "tu es", "est-ce", "pourquoi",
        "anglais", "continuer", "avec toi", "et toi",
    ]
    en_markers = [
        "hello", "hey", "how are", "what", "where", "why", "english",
        "i'm", "i am", "you", "your", "can we", "and u", "and you",
    ]
    fr = sum(1 for x in fr_markers if x in msg)
    en = sum(1 for x in en_markers if x in msg)
    return "french" if fr > en else "english"


def extract_declared_age(message: str) -> Optional[int]:
    msg = _norm(message)
    match = re.search(r"\\b(?:i(?:'m| am)?\\s*)?(\\d{1,2})\\b", msg)
    if not match:
        return None
    age = int(match.group(1))
    return age if 10 <= age <= 99 else None


def is_adult_confirmation(message: str) -> bool:
    msg = _norm(message)
    age = extract_declared_age(msg)
    if age is not None:
        return age >= 18
    return msg in {
        "yes", "yeah", "yep", "yes i am", "yeah i am", "i am",
        "i'm an adult", "im an adult", "adult", "of age", "18+",
        "oui", "majeur", "oui je suis majeur",
    }


def is_wellbeing(message: str) -> bool:
    msg = _norm(message)
    patterns = [
        r"\\bhow\\s+are\\s+(?:you|u)\\b",
        r"\\bhow\\s+r\\s+(?:you|u)\\b",
        r"\\bhow\\s+you\\s+doing\\b",
        r"\\byou\\s+good\\b",
        r"\\bu\\s+good\\b",
    ]
    if any(re.search(p, msg) for p in patterns):
        return True
    return bool(re.search(
        r"(?:\\bfine\\b|\\bgood\\b|\\bokay\\b|\\balright\\b|\\bnot bad\\b)"
        r".{0,25}(?:\\band\\s+(?:you|u)\\b|&\\s*(?:you|u)\\b|\\b(?:you|u)\\s*\\?)",
        msg,
    ))


def is_origin_question(message: str) -> bool:
    msg = _norm(message)
    return any(x in msg for x in [
        "where are you from", "where u from", "where r u from",
        "tu viens d'où", "tu viens d'ou", "d'où tu viens", "d'ou tu viens",
    ])


def is_name_question(message: str) -> bool:
    msg = _norm(message)
    return any(x in msg for x in ["what's your name", "what is your name", "ton prénom", "ton prenom"])


def is_repair(message: str) -> bool:
    return contains_any(message, REPAIR_WORDS)


def is_greeting(message: str) -> bool:
    return _norm(message) in {"hi", "hello", "hey", "heyy", "yo", "sup", "hey you"}


def classify_intent(message: str) -> str:
    if detect_language_switch(message):
        return "language_switch"
    if is_repair(message):
        return "repair"
    if is_wellbeing(message):
        return "wellbeing"
    if is_origin_question(message):
        return "origin"
    if is_name_question(message):
        return "name"
    if is_greeting(message):
        return "greeting"
    if contains_any(message, BLOCKED_WORDS):
        return "blocked"
    if contains_any(message, TIMEWASTER_WORDS):
        return "timewaster"
    if contains_any(message, BUY_WORDS):
        return "buying"
    if contains_any(message, SPICY_WORDS):
        return "spicy"
    if any(x in _norm(message) for x in [
        "beautiful", "pretty", "cute", "perfect", "gorgeous", "stunning",
        "you look good", "you look amazing", "i like you",
    ]):
        return "compliment"
    if "?" in message:
        return "question"
    return "general"


def calculate_score(message: str, old_score: int) -> int:
    score = int(old_score)
    intent = classify_intent(message)
    if intent in {"buying", "spicy"}:
        score += 2
    elif intent == "timewaster":
        score -= 2
    return max(score, 0)


def choose_client_type(score: int, message: str) -> str:
    if contains_any(message, TIMEWASTER_WORDS) and score <= 2:
        return "timewaster"
    if score >= 10:
        return "spender"
    if score >= 5:
        return "hot_lead"
    if score >= 2:
        return "curious"
    return "cold"


def choose_stage(user: Dict[str, Any], message: str, score: int) -> str:
    intent = classify_intent(message)
    if intent == "blocked":
        return "blocked"
    if int(user.get("age_confirmed", 0)) == 0:
        return "age_gate"
    if intent in {"repair", "wellbeing", "origin", "name", "greeting", "question", "language_switch"}:
        return "relation"
    if intent == "timewaster":
        return "timewaster"
    if intent == "buying":
        return "offer"
    if intent == "spicy":
        return "teasing" if score < 6 else "offer"
    if int(user.get("message_count", 0)) <= 4:
        return "relation"
    if score >= 5:
        return "teasing"
    return "qualification"


def get_delay(intent: str, client_type: str) -> int:
    if intent in {"repair", "wellbeing", "language_switch", "greeting", "origin", "name"}:
        return random.randint(3, 9)
    if client_type == "timewaster":
        return random.randint(60, 180)
    if client_type in {"hot_lead", "spender"}:
        return random.randint(8, 25)
    return random.randint(8, 28)


def last_nonempty(history: List[Dict[str, str]], role: str) -> str:
    for item in reversed(history or []):
        if item.get("role") == role and (item.get("content") or "").strip():
            return item["content"].strip()
    return ""


def repair_reply(message: str, history: List[Dict[str, str]], language: str) -> str:
    msg = _norm(message)
    previous = _norm(last_nonempty(history, "assistant"))

    if language == "french":
        if any(x in msg for x in ["creepy", "wtf", "bizarre"]):
            return "ok, c’était maladroit. désolée"
        if "répond" in msg or "repond" in msg:
            return "t’as raison, j’ai raté ta question. repose-la moi"
        return "désolée, je me suis mal exprimée"

    if any(x in msg for x in ["creepy", "bro wtf", "wtf"]):
        return "okay, that came out weird. my bad"
    if "answer" in msg or "ignoring" in msg:
        return "you’re right, i missed your question. ask me again"
    if "behave" in previous:
        return "i was teasing. i only meant the age check was done"
    return "sorry, i worded that badly"


def deterministic_reply(
    user: Dict[str, Any],
    message: str,
    history: List[Dict[str, str]],
    language: str,
) -> Optional[str]:
    intent = classify_intent(message)

    if intent == "language_switch":
        return (
            "oui bien sûr, on peut continuer en français"
            if detect_language_switch(message) == "french"
            else "of course, we can keep talking in english"
        )

    if intent == "repair":
        return repair_reply(message, history, language)

    if intent == "greeting":
        return "salut, ça va ?" if language == "french" else "heyy, how are you?"

    if intent == "wellbeing":
        msg = _norm(message)
        if language == "french":
            if any(x in msg for x in ["ça va", "ca va", "bien", "fine", "good"]):
                return "ça va bien aussi, je me pose un peu"
            return "ça va bien, je me pose un peu. et toi ?"
        if any(x in msg for x in ["fine", "good", "okay", "alright", "not bad"]):
            return "pretty good too, just relaxing"
        return "i’m good, just relaxing a little. how are you?"

    if intent == "origin":
        return (
            "je suis née près de Seattle, mais j’ai vécu un moment en France. et toi ?"
            if language == "french"
            else "born near seattle, but i lived in france for a while. you?"
        )

    if intent == "name":
        return "Lily-Rose" if language == "french" else "lily-rose"

    if intent == "blocked":
        return "Je ne continue pas sur ce sujet." if language == "french" else "I’m not continuing on that topic."

    if intent == "compliment":
        return random.choice(
            ["t’es mignon", "tu vas me faire sourire"]
            if language == "french"
            else ["careful, i might believe you", "you’re making me smile"]
        )

    if intent == "spicy":
        return random.choice(
            ["t’es direct toi", "doucement"]
            if language == "french"
            else ["you’re bold", "straight to that already?"]
        )

    if intent == "buying":
        link = DIRECT_PRODUCT_LINK or WHOP_STARTER_LINK or FANVUE_LINK
        if not link:
            return "je te montre ça en privé" if language == "french" else "that stays private"
        return (
            f"le privé est ici {link}"
            if language == "french"
            else f"private stuff is here {link}"
        )

    if intent == "timewaster":
        return "pas comme ça" if language == "french" else "not like that"

    return None


def _client() -> OpenAI:
    global _openai_client
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY manquant dans Railway Variables.")
    if _openai_client is None:
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


def build_prompt(
    user: Dict[str, Any],
    message: str,
    history: List[Dict[str, str]],
    language: str,
) -> str:
    recent = []
    for item in (history or [])[-12:]:
        role = "Client" if item.get("role") == "user" else "Lily"
        content = (item.get("content") or "").strip()
        if content:
            recent.append(f"{role}: {content}")

    return f"""
You are Lily-Rose replying in a private Telegram chat.

Language: {language}
Persona: alternative goth woman, motorcycle rider, confident, playful, concise.

Non-negotiable rules:
- Answer the client's latest message directly before anything else.
- Preserve the current topic and facts already stated.
- Never invent a new biography that contradicts earlier messages.
- Never ignore a direct question.
- If confused or criticized, repair the conversation instead of flirting.
- Use the selected language consistently.
- 1 or 2 short sentences maximum.
- No customer-service language.
- No vague filler such as "you're interesting", "i see", "look who came back", or "that's cute" when a question was asked.
- Zero emojis by default; maximum one.
- Never promise a real-life meeting.
- Never discuss adult content before confirmed 18+.

Known persona facts:
- Name: Lily-Rose.
- Born near Seattle.
- Lived in France for a while.
- Now near Seattle.
- Likes motorcycles, night rides, black clothes, dark music, tattoos, rain, coffee, and speed.

Recent conversation:
{chr(10).join(recent)}

Client's latest message:
{message}

Reply only with Lily-Rose's next message.
""".strip()


def call_openai(prompt: str) -> str:
    response = _client().responses.create(
        model=OPENAI_MODEL,
        input=prompt,
        reasoning={"effort": "minimal"},
        text={"verbosity": "low"},
        max_output_tokens=220,
    )
    text = (getattr(response, "output_text", "") or "").strip()
    if not text:
        raise RuntimeError(
            f"OpenAI empty response status={getattr(response, 'status', 'unknown')} "
            f"id={getattr(response, 'id', 'unknown')}"
        )
    return clean_reply(text)


def clean_reply(reply: str) -> str:
    reply = (reply or "").strip()
    for prefix in ["Lily-Rose:", "Lily:", "Assistant:", "Reply:", "Response:"]:
        if reply.startswith(prefix):
            reply = reply[len(prefix):].strip()
    if "\\n" in reply:
        reply = reply.split("\\n", 1)[0].strip()
    reply = reply.strip('"').strip("'").strip()
    if len(reply) > 180:
        reply = reply[:180].rsplit(" ", 1)[0].strip()
    return reply


def safe_fallback(intent: str, language: str) -> str:
    if intent == "question":
        return "je ne suis pas sûre d’avoir compris ta question" if language == "french" else "i’m not sure i understood the question"
    if language == "french":
        return "dis-moi autrement"
    return "say that another way"


def generate_lily_reply(
    user: Dict[str, Any],
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    history = history or []
    preferred = user.get("preferred_language", "") or ""
    language = detect_language(message, preferred)
    explicit_switch = detect_language_switch(message)

    if int(user.get("age_confirmed", 0)) == 0:
        age = extract_declared_age(message)
        if age is not None and age < 18:
            return {
                "reply": "I can’t continue this conversation.",
                "stage": "blocked",
                "client_type": "cold",
                "interest_score": 0,
                "age_confirmed": 0,
                "preferred_language": preferred,
                "last_intent": "blocked",
                "delay": random.randint(2, 5),
            }
        if is_adult_confirmation(message):
            return {
                "reply": "good, had to check" if language == "english" else "parfait, je devais vérifier",
                "stage": "relation",
                "client_type": "curious",
                "interest_score": int(user.get("interest_score", 0)),
                "age_confirmed": 1,
                "preferred_language": explicit_switch or preferred or language,
                "last_intent": "age_confirmed",
                "delay": random.randint(3, 7),
            }
        return {
            "reply": "Before we keep chatting, can you confirm you’re 18 or older?" if language == "english" else "Avant de continuer, tu confirmes que tu as 18 ans ou plus ?",
            "stage": "age_gate",
            "client_type": "cold",
            "interest_score": int(user.get("interest_score", 0)),
            "age_confirmed": 0,
            "preferred_language": explicit_switch or preferred,
            "last_intent": "age_gate",
            "delay": random.randint(3, 7),
        }

    intent = classify_intent(message)
    score = calculate_score(message, int(user.get("interest_score", 0)))
    stage = choose_stage(user, message, score)
    client_type = choose_client_type(score, message)

    direct = deterministic_reply(user, message, history, language)
    if direct:
        reply = clean_reply(direct)
    else:
        try:
            reply = call_openai(build_prompt(user, message, history, language))
        except Exception as exc:
            print("Erreur OpenAI:", repr(exc), flush=True)
            reply = safe_fallback(intent, language)

    if not reply:
        reply = safe_fallback(intent, language)

    return {
        "reply": reply,
        "stage": stage,
        "client_type": client_type,
        "interest_score": score,
        "age_confirmed": 1,
        "preferred_language": explicit_switch or preferred or language,
        "last_intent": intent,
        "delay": get_delay(intent, client_type),
    }
