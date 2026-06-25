import os
import random
import re
from typing import Any, Dict, List, Optional

from openai import OpenAI

BOT_VERSION = "v11.0-adaptive"
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
    pattern = r"(?<!\\w)" + re.escape(phrase) + r"(?!\\w)"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def contains_any(text: str, phrases: List[str]) -> bool:
    return any(_whole_match(text, phrase) for phrase in phrases)


BLOCKED_WORDS = [
    "minor", "under 18", "underage", "child", "15 years old",
    "16 years old", "17 years old", "mineur", "moins de 18", "enfant",
    "rape", "force", "blackmail", "threat", "incest",
    "viol", "forcer", "chantage", "menace", "inceste",
]

SPICY_WORDS = [
    "nude", "nudes", "naked", "boobs", "tits", "ass", "pussy",
    "show me", "send me", "hot pics", "sexy pics", "your body",
    "nue", "nu", "seins", "cul", "fesses", "coquine", "sexy",
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
    "je comprends pas", "je ne comprends pas", "tu réponds pas",
]

WARM_WORDS = [
    "miss you", "i like you", "i love you", "you're sweet", "you are sweet",
    "tu me plais", "je t'aime bien", "tu es mignonne", "tu es belle",
]

RUDE_WORDS = [
    "idiot", "stupid", "bitch", "fuck you", "ferme ta gueule", "connasse",
]


def detect_language_switch(message: str) -> Optional[str]:
    msg = _norm(message)
    french = [
        "continuer en français", "continuer en francais", "parler français",
        "parler francais", "on peut parler français", "on peut parler francais",
        "can we speak french", "speak french please", "je ne parle pas anglais",
        "je parle pas anglais",
    ]
    english = [
        "continue in english", "speak english", "can we speak english",
        "english please", "je préfère l'anglais", "je prefere l'anglais",
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
        "anglais", "continuer", "avec toi", "et toi", "mais", "car",
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
        r"\\bça va\\b",
        r"\\bca va\\b",
    ]
    if any(re.search(p, msg) for p in patterns):
        return True
    return bool(re.search(
        r"(?:\\bfine\\b|\\bgood\\b|\\bokay\\b|\\balright\\b|\\bnot bad\\b|\\bbien\\b)"
        r".{0,25}(?:\\band\\s+(?:you|u)\\b|&\\s*(?:you|u)\\b|\\b(?:you|u)\\s*\\?|\\bet toi\\b)",
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


def is_greeting(message: str) -> bool:
    return _norm(message) in {"hi", "hello", "hey", "heyy", "yo", "sup", "hey you", "salut", "coucou"}


def classify_intent(message: str) -> str:
    if detect_language_switch(message):
        return "language_switch"
    if contains_any(message, BLOCKED_WORDS):
        return "blocked"
    if contains_any(message, REPAIR_WORDS):
        return "repair"
    if is_wellbeing(message):
        return "wellbeing"
    if is_origin_question(message):
        return "origin"
    if is_name_question(message):
        return "name"
    if is_greeting(message):
        return "greeting"
    if contains_any(message, TIMEWASTER_WORDS):
        return "timewaster"
    if contains_any(message, BUY_WORDS):
        return "buying"
    if contains_any(message, SPICY_WORDS):
        return "spicy"
    if contains_any(message, WARM_WORDS):
        return "warm"
    if contains_any(message, RUDE_WORDS):
        return "rude"
    if any(x in _norm(message) for x in [
        "beautiful", "pretty", "cute", "perfect", "gorgeous", "stunning",
        "you look good", "you look amazing", "i like you", "belle", "magnifique",
    ]):
        return "compliment"
    if "?" in message:
        return "question"
    return "general"


def calculate_score(message: str, old_score: int) -> int:
    score = int(old_score)
    intent = classify_intent(message)
    if intent == "buying":
        score += 3
    elif intent == "spicy":
        score += 2
    elif intent in {"warm", "compliment"}:
        score += 1
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
    if intent in {"repair", "wellbeing", "origin", "name", "greeting", "question", "language_switch", "warm", "compliment"}:
        return "relation"
    if intent == "timewaster":
        return "timewaster"
    if intent == "buying":
        return "offer"
    if intent == "spicy":
        return "teasing" if score < 7 else "offer"
    if int(user.get("message_count", 0)) <= 4:
        return "relation"
    if score >= 5:
        return "teasing"
    return "qualification"


def choose_tone(user: Dict[str, Any], message: str, history: List[Dict[str, str]]) -> str:
    intent = classify_intent(message)
    msg = _norm(message)

    if intent == "repair":
        return "repair"
    if intent == "rude":
        return "firm"
    if intent in {"warm", "compliment"}:
        return "warm"
    if intent == "spicy":
        return "playful_spicy"
    if intent == "buying":
        return "confident_sales"
    if intent in {"wellbeing", "greeting", "origin", "name"}:
        return "warm_casual"
    if "haha" in msg or "lol" in msg or ":p" in msg or "^^" in msg:
        return "playful"

    previous = user.get("conversation_tone", "") or ""
    return previous if previous in {
        "warm", "warm_casual", "playful", "playful_spicy", "confident_sales", "firm"
    } else "balanced"


def get_delay(intent: str, client_type: str) -> int:
    if intent in {"repair", "wellbeing", "language_switch", "greeting", "origin", "name"}:
        return random.randint(3, 8)
    if intent in {"spicy", "buying", "compliment", "warm"}:
        return random.randint(5, 14)
    if client_type == "timewaster":
        return random.randint(40, 100)
    if client_type in {"hot_lead", "spender"}:
        return random.randint(6, 18)
    return random.randint(7, 22)


def last_nonempty(history: List[Dict[str, str]], role: str) -> str:
    for item in reversed(history or []):
        if item.get("role") == role and (item.get("content") or "").strip():
            return item["content"].strip()
    return ""


def count_intent(history: List[Dict[str, str]], phrases: List[str]) -> int:
    count = 0
    for item in history or []:
        if item.get("role") == "user" and contains_any(item.get("content", ""), phrases):
            count += 1
    return count


def repair_reply(message: str, history: List[Dict[str, str]], language: str) -> str:
    msg = _norm(message)
    previous = _norm(last_nonempty(history, "assistant"))

    if language == "french":
        if any(x in msg for x in ["creepy", "wtf", "bizarre"]):
            return "ok, c’était maladroit, désolée"
        if "répond" in msg or "repond" in msg:
            return "tu as raison, j’ai raté ta question, repose-la moi"
        if "anglais" in msg:
            return "désolée, je reste en français"
        return "désolée, je me suis mal exprimée"

    if any(x in msg for x in ["creepy", "bro wtf", "wtf"]):
        return "okay, that came out weird, my bad"
    if "answer" in msg or "ignoring" in msg:
        return "you’re right, i missed your question, ask me again"
    if "behave" in previous:
        return "i was teasing, i only meant the age check was done"
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
            "oui bien sûr, on continue en français"
            if detect_language_switch(message) == "french"
            else "of course, we can keep talking in english"
        )

    if intent == "repair":
        return repair_reply(message, history, language)

    if intent == "greeting":
        return random.choice(
            ["salut toi, ça va ?", "coucou, comment tu vas ?"]
            if language == "french"
            else ["heyy, how are you?", "hey you, how’s your day going?"]
        )

    if intent == "wellbeing":
        msg = _norm(message)
        if language == "french":
            if any(x in msg for x in ["bien", "fine", "good"]):
                return random.choice(["ça va bien aussi, je me pose un peu", "plutôt bien, journée tranquille"])
            return random.choice(["ça va bien, je me pose un peu, et toi ?", "plutôt bien aujourd’hui, et toi ?"])
        if any(x in msg for x in ["fine", "good", "okay", "alright", "not bad"]):
            return random.choice(["pretty good too, just relaxing", "i’m good too, taking it easy"])
        return random.choice(["i’m good, just relaxing a little, how are you?", "pretty good actually, how about you?"])

    if intent == "origin":
        return (
            "je suis née près de Seattle, mais j’ai vécu un moment en France, et toi ?"
            if language == "french"
            else "born near seattle, but i lived in france for a while, you?"
        )

    if intent == "name":
        return "Lily-Rose"

    if intent == "blocked":
        return "Je ne continue pas sur ce sujet." if language == "french" else "I’m not continuing on that topic."

    if intent == "compliment":
        return random.choice(
            ["merci, tu sais parler aux filles toi", "ça me fait sourire, j’avoue"]
            if language == "french"
            else ["careful, i might believe you", "okay, that made me smile"]
        )

    if intent == "warm":
        return random.choice(
            ["c’est mignon ça", "tu deviens attachant toi"]
            if language == "french"
            else ["that’s actually sweet", "you’re getting kinda cute"]
        )

    if intent == "timewaster":
        return "pas comme ça" if language == "french" else "not like that"

    if intent == "rude":
        return "calme-toi un peu" if language == "french" else "easy, don’t talk to me like that"

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
    tone: str,
    intent: str,
) -> str:
    recent = []
    for item in (history or [])[-16:]:
        role = "Client" if item.get("role") == "user" else "Lily"
        content = (item.get("content") or "").strip()
        if content:
            recent.append(f"{role}: {content}")

    spicy_count = count_intent(history, SPICY_WORDS)
    buying_count = count_intent(history, BUY_WORDS)

    return f"""
You are Lily-Rose replying in a private Telegram conversation.

Language: {language}
Current tone: {tone}
Current intent: {intent}
Spicy signals in recent chat: {spicy_count}
Buying signals in recent chat: {buying_count}

Personality:
- Alternative goth woman, motorcycle rider, confident and feminine.
- Warm when the client is warm, playful when he is playful, firm when he is disrespectful.
- Never permanently cold or permanently cheerful.
- She reacts to the exact moment and adjusts naturally.
- She can be suggestive and a little crude with a confirmed adult, but not graphic or explicit.
- She knows how to build tension without sounding like a salesperson.

Style rules:
- Answer the latest message directly first.
- Keep the current topic and facts consistent.
- 1 or 2 short sentences maximum.
- No em dashes, no long dash punctuation, no semicolons.
- No canned phrases like "you're bold", "i see", "look who came back", "you're interesting".
- No customer service tone.
- Zero emojis by default, maximum one when it fits naturally.
- Never mix languages unless the client mixes them and clearly enjoys it.
- If the client asked to stay in French, stay entirely in French.
- If the client is warm, be warmer.
- If he is flirty, mirror him a little and increase tension.
- If he becomes sexual, do not freeze and do not reply with a generic canned line.
- For a first sexual message, tease and qualify what he likes.
- For repeated sexual interest, create tension and guide toward private content naturally.
- For clear buying intent, send the most relevant link once, without sounding robotic.
- Never promise a real-life meeting.
- Never engage with underage, coercive, violent, incestuous, or illegal content.

Known facts:
- Name: Lily-Rose.
- Born near Seattle.
- Lived in France for a while.
- Now near Seattle.
- Likes motorcycles, night rides, black clothes, dark music, tattoos, rain, coffee, and speed.
- Fanvue: {FANVUE_LINK}
- Direct private link: {DIRECT_PRODUCT_LINK or WHOP_STARTER_LINK}

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
        max_output_tokens=260,
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
    reply = reply.replace("—", ",").replace("–", ",")
    reply = re.sub(r"\\s+,", ",", reply)
    reply = re.sub(r"\\s{2,}", " ", reply)
    banned = {
        "you're bold", "you’re bold", "i see", "look who came back",
        "you're interesting", "you’re interesting", "that's cute", "that’s cute",
    }
    if _norm(reply) in banned:
        return ""
    if len(reply) > 220:
        reply = reply[:220].rsplit(" ", 1)[0].strip()
    return reply


def safe_fallback(intent: str, language: str, tone: str, history: List[Dict[str, str]]) -> str:
    if intent == "spicy":
        return random.choice(
            ["tu vas vite toi, qu’est-ce qui te plaît le plus ?", "mmh, tu sais être direct, tu veux voir quoi exactement ?"]
            if language == "french"
            else ["you move fast, what do you wanna see most?", "mm, you know how to be direct, what are you after exactly?"]
        )
    if intent == "buying":
        link = DIRECT_PRODUCT_LINK or WHOP_STARTER_LINK or FANVUE_LINK
        if link:
            return (f"si tu veux vraiment voir, c’est ici {link}" if language == "french" else f"if you really wanna see, it’s here {link}")
    if intent == "question":
        return "je ne suis pas sûre d’avoir compris ta question" if language == "french" else "i’m not sure i understood the question"
    if tone in {"warm", "warm_casual"}:
        return "c’est mignon ça" if language == "french" else "that’s actually sweet"
    return "dis-moi autrement" if language == "french" else "say that another way"


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
                "conversation_tone": "firm",
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
                "conversation_tone": "warm_casual",
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
            "conversation_tone": "neutral",
            "delay": random.randint(3, 7),
        }

    intent = classify_intent(message)
    score = calculate_score(message, int(user.get("interest_score", 0)))
    stage = choose_stage(user, message, score)
    client_type = choose_client_type(score, message)
    tone = choose_tone(user, message, history)

    direct = deterministic_reply(user, message, history, language)
    if direct:
        reply = clean_reply(direct)
    else:
        try:
            reply = call_openai(build_prompt(user, message, history, language, tone, intent))
        except Exception as exc:
            print("Erreur OpenAI:", repr(exc), flush=True)
            reply = safe_fallback(intent, language, tone, history)

    if not reply:
        reply = safe_fallback(intent, language, tone, history)

    return {
        "reply": reply,
        "stage": stage,
        "client_type": client_type,
        "interest_score": score,
        "age_confirmed": 1,
        "preferred_language": explicit_switch or preferred or language,
        "last_intent": intent,
        "conversation_tone": tone,
        "delay": get_delay(intent, client_type),
    }
