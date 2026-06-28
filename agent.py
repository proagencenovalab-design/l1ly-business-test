import os
import random
import re
from typing import Any, Dict, List, Optional

from openai import OpenAI

BOT_VERSION = "v11.2-agegate-strict"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini").strip()

FANVUE_LINK = os.getenv("FANVUE_LINK", "").strip()
DIRECT_PRODUCT_LINK = os.getenv("DIRECT_PRODUCT_LINK", "").strip()
WHOP_STARTER_LINK = os.getenv("WHOP_STARTER_LINK", "").strip()
WHOP_PREMIUM_LINK = os.getenv("WHOP_PREMIUM_LINK", "").strip()
WHOP_VIP_LINK = os.getenv("WHOP_VIP_LINK", "").strip()

# Commercial offer configuration.
# VIP is disabled because it does not exist yet.
STARTER_PRICE = "29,99€"
STARTER_CONTENT = "4 images NSFW + 1 vidéo solo"
STARTER_LINK = WHOP_STARTER_LINK or DIRECT_PRODUCT_LINK

PREMIUM_PRICE = "75€"
PREMIUM_CONTENT = "3 vidéos + 5 images"
PREMIUM_LINK = WHOP_PREMIUM_LINK

VIP_ENABLED = False
VIP_LINK = ""

OFFER_COOLDOWN_MESSAGES = int(os.getenv("OFFER_COOLDOWN_MESSAGES", "7"))


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
    "where can i see", "where to see", "unlock", "send the link",
    "exclusive", "more exclusive", "video", "videos",
    "prix", "tarif", "combien", "payer", "acheter", "contenu privé",
    "plus exclusif", "exclusif", "où voir", "ou voir", "envoie le lien",
    "donne le lien", "vidéo", "vidéos",
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



def is_direct_buying_question(message: str) -> bool:
    msg = _norm(message)
    patterns = [
        "prix", "tarif", "combien", "payer", "acheter", "lien",
        "envoie le lien", "donne le lien", "où voir", "ou voir",
        "plus exclusif", "exclusif", "price", "how much", "cost",
        "link", "where can i see", "where to see", "unlock",
    ]
    return any(pattern in msg for pattern in patterns)


def has_offer_cooldown(user: Dict[str, Any], allow_if_direct_buying: bool = False, message: str = "") -> bool:
    if allow_if_direct_buying and is_direct_buying_question(message):
        return False
    last_offer = int(user.get("last_offer_message_count") or 0)
    message_count = int(user.get("message_count") or 0)
    if last_offer <= 0:
        return False
    return (message_count - last_offer) < OFFER_COOLDOWN_MESSAGES


def select_offer(message: str, user: Dict[str, Any]) -> Dict[str, str]:
    msg = _norm(message)
    if any(x in msg for x in ["premium", "plus exclusif", "exclusif", "more exclusive", "vidéo", "video", "videos", "vidéos"]):
        return {"name": "Premium", "price": PREMIUM_PRICE, "content": PREMIUM_CONTENT, "link": PREMIUM_LINK or STARTER_LINK}
    return {"name": "Starter", "price": STARTER_PRICE, "content": STARTER_CONTENT, "link": STARTER_LINK}


def short_offer_reply(message: str, language: str, user: Dict[str, Any]) -> str:
    offer = select_offer(message, user)
    link = offer.get("link") or DIRECT_PRODUCT_LINK or FANVUE_LINK
    if not link:
        return "je te montre ça en privé, mais le lien n’est pas prêt là" if language == "french" else "i keep that private, but the link isn’t ready right now"
    if language == "french":
        if offer["name"].lower() == "premium":
            return f"si tu veux le plus complet, prends le Premium: {offer['price']}, {offer['content']}. {link}"
        return f"commence par le Starter: {offer['price']}, {offer['content']}. {link}"
    if offer["name"].lower() == "premium":
        return f"if you want the full one, Premium is {offer['price']}: {offer['content']}. {link}"
    return f"start with Starter: {offer['price']}: {offer['content']}. {link}"


def first_spicy_reaction(language: str) -> str:
    return random.choice(
        ["tu sais déjà ce que tu veux toi", "t’es direct, j’aime bien", "mmh, tu ne perds pas de temps", "je vois très bien ce que tu veux"]
        if language == "french"
        else ["you know exactly what you want", "you’re direct, i like that", "mm, you don’t waste time", "i see what you came for"]
    )


def second_spicy_reaction(language: str) -> str:
    return random.choice(
        ["je garde ça dans mon privé, pas en public ici", "ça je le garde pour le privé", "si je te montre ça, ce sera pas comme un aperçu gratuit", "tu veux du soft ou tu veux vraiment le plus chaud ?"]
        if language == "french"
        else ["i keep that in private, not out here", "that part stays private", "if i show you that, it won’t be a free preview", "you want soft or the hotter one?"]
    )


def should_send_offer_now(user: Dict[str, Any], message: str, history: List[Dict[str, str]], intent: str) -> bool:
    if has_offer_cooldown(user, allow_if_direct_buying=True, message=message):
        return False
    spicy_count = count_intent(history, SPICY_WORDS)
    buying_count = count_intent(history, BUY_WORDS)
    if intent == "buying":
        return True
    if is_direct_buying_question(message):
        return True
    if intent == "spicy" and spicy_count >= 2:
        return True
    if buying_count >= 1 and intent == "spicy":
        return True
    return False


def mark_offer_sent_if_needed(reply: str) -> bool:
    reply = reply or ""
    links = [STARTER_LINK, PREMIUM_LINK, DIRECT_PRODUCT_LINK, WHOP_STARTER_LINK, WHOP_PREMIUM_LINK, FANVUE_LINK]
    return any(link and link in reply for link in links)


def choose_stage(user: Dict[str, Any], message: str, score: int) -> str:
    intent = classify_intent(message)
    if is_direct_buying_question(message):
        return "offer"
    if intent == "blocked":
        return "blocked"
    if int(user.get("age_confirmed", 0)) == 0:
        return "age_gate"
    if intent in {"repair", "wellbeing", "origin", "name", "greeting", "question", "language_switch", "warm", "compliment"}:
        return "relation"
    if intent == "timewaster":
        return "pas comme ça" if language == "french" else "not like that"

    if intent in {"spicy", "buying"} or is_direct_buying_question(message):
        if should_send_offer_now(user, message, history, intent):
            return short_offer_reply(message, language, user)

        spicy_count = count_intent(history, SPICY_WORDS)
        if spicy_count <= 1:
            return first_spicy_reaction(language)

        return second_spicy_reaction(language)

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
- Do not ask more than one question in a row unless the client is confused.
- Sometimes react without a question and let the client chase.
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

Commercial reality:
- Starter exists: 29,99€, 4 images NSFW + 1 vidéo solo.
- Premium exists: 75€, 3 vidéos + 5 images.
- VIP does not exist. Never sell VIP, never mention VIP as available.
- Do not invent custom requests, direct access, set themes, video calls, meetings, or special services.
- Telegram can be used for chat and teasing, but do not say a photo/video has already been sent unless the system actually sends media.
- When the client clearly asks price/link/where to see, send the relevant Whop link once.
- After sending a link, do not push another paid offer for at least 7 client messages unless he asks price/link again.
- If he says he wants to stay here, continue tension and conversation without pushing a link immediately.
- For BDSM/domination fantasies, qualify and build tension, but do not invent a product that does not exist.

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
    if "\n" in reply:
        reply = reply.split("\n", 1)[0].strip()
    reply = reply.strip('"').strip("'").strip()
    reply = reply.replace("—", ",").replace("–", ",")
    reply = re.sub(r"\s+,", ",", reply)
    reply = re.sub(r"\s{2,}", " ", reply)

    banned = {
        "you're bold", "you’re bold", "i see", "look who came back",
        "you're interesting", "you’re interesting", "that's cute", "that’s cute",
    }
    if _norm(reply) in banned:
        return ""

    if reply.count("😉") > 1:
        reply = reply.replace("😉", "").strip()
    elif reply.count("😉") == 1 and random.random() < 0.55:
        reply = reply.replace("😉", "").strip()

    has_link = "http://" in reply or "https://" in reply
    max_len = 190 if has_link else 125
    if len(reply) > max_len:
        reply = reply[:max_len].rsplit(" ", 1)[0].strip()

    incomplete_endings = {"ou", "or", "et", "and", "mais", "but", "avec", "with", "pour", "for", "classic", "classique"}
    words = reply.rstrip(" ?!,.").split()
    if words and _norm(words[-1]) in incomplete_endings:
        reply = " ".join(words[:-1]).rstrip(" ,")

    return reply.strip()


def safe_fallback(intent: str, language: str, tone: str, history: List[Dict[str, str]]) -> str:
    if intent == "spicy":
        return random.choice(
            ["tu sais déjà ce que tu veux toi", "mmh, tu ne perds pas de temps", "je vois très bien ce que tu veux"]
            if language == "french"
            else ["you know exactly what you want", "mm, you don’t waste time", "i see what you came for"]
        )
    if intent == "buying":
        link = DIRECT_PRODUCT_LINK or WHOP_STARTER_LINK or FANVUE_LINK
        if link:
            return (f"commence par le Starter: {STARTER_PRICE}, {STARTER_CONTENT}. {link}" if language == "french" else f"start with Starter: {STARTER_PRICE}, {STARTER_CONTENT}. {link}")
    if intent == "question":
        return "je ne suis pas sûre d’avoir compris ta question" if language == "french" else "i’m not sure i understood the question"
    if tone in {"warm", "warm_casual"}:
        return "c’est mignon ça" if language == "french" else "that’s actually sweet"
    return "dis-moi autrement" if language == "french" else "say that another way"



def age_gate_followup_reply(language: str, age_gate_count: int) -> Dict[str, Any]:
    """
    The prospect didn't answer the age question.
    Do not restart the soft age gate. Escalate once, then end/stop.
    """
    if age_gate_count == 1:
        return {
            "reply": (
                "tu n’as pas répondu à ma question, c’est important. dis-moi juste si t’es majeur, sinon je préfère arrêter là"
                if language == "french"
                else "you didn’t answer my question, it’s important. just tell me if you’re 18+, otherwise i’d rather stop here"
            ),
            "skip_send": False,
            "age_gate_count": 2,
        }

    if age_gate_count == 2:
        return {
            "reply": (
                "je préfère être honnête, sans confirmation que t’es majeur je dois mettre fin à la discussion"
                if language == "french"
                else "i’d rather be honest, without confirmation that you’re 18+ i have to end the conversation"
            ),
            "skip_send": False,
            "age_gate_count": 3,
        }

    return {"reply": "", "skip_send": True, "age_gate_count": age_gate_count + 1}



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
                "reply": (
                    random.choice(["good, had to make sure 😂", "okay perfect, i just had to check", "good, you’re safe then"])
                    if language == "english"
                    else random.choice(["parfait, je préférais vérifier 😂", "ok nickel, je voulais juste être sûre", "parfait, t’es safe alors"])
                ),
                "stage": "relation",
                "client_type": "curious",
                "interest_score": int(user.get("interest_score", 0)),
                "age_confirmed": 1,
                "preferred_language": explicit_switch or preferred or language,
                "last_intent": "age_confirmed",
                "conversation_tone": "warm_casual",
                "age_gate_count": 0,
                "delay": random.randint(3, 7),
            }
        age_gate_replies = {
            "french": [
                "attends, avant que je te réponde… t’es bien majeur au moins ? j’ai pas envie d’avoir des problèmes moi 😂",
                "attends deux secondes, t’as bien 18 ans ou plus ? je préfère vérifier avant de répondre à ça 😂",
                "juste pour être sûre… t’es majeur au moins ? j’ai pas envie de finir dans les problèmes à cause de toi 😭",
                "avant que je te réponde, dis-moi juste que t’as bien 18 ans, je préfère vérifier",
            ],
            "english": [
                "wait, before i answer that… you’re 18 or older, right? i’m not trying to get myself in trouble 😂",
                "hold on, you’re definitely 18+, right? i’d rather check before i answer that 😂",
                "just making sure… you’re an adult, right? i’m not getting in trouble because of you 😭",
                "before i answer, tell me you’re 18 or older. i’d rather be safe",
            ],
        }
        age_gate_count = int(user.get("age_gate_count") or 0)

        if age_gate_count <= 0:
            return {
                "reply": random.choice(age_gate_replies[language]),
                "stage": "age_gate",
                "client_type": "cold",
                "interest_score": int(user.get("interest_score", 0)),
                "age_confirmed": 0,
                "preferred_language": explicit_switch or preferred,
                "last_intent": "age_gate",
                "conversation_tone": "warm_casual",
                "age_gate_count": 1,
                "delay": random.randint(3, 7),
            }

        followup = age_gate_followup_reply(language, age_gate_count)
        return {
            "reply": followup["reply"],
            "skip_send": followup["skip_send"],
            "stage": "age_gate",
            "client_type": "cold",
            "interest_score": int(user.get("interest_score", 0)),
            "age_confirmed": 0,
            "preferred_language": explicit_switch or preferred,
            "last_intent": "age_gate_ignored",
            "conversation_tone": "firm",
            "age_gate_count": followup["age_gate_count"],
            "delay": random.randint(2, 5),
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
        "offer_sent": mark_offer_sent_if_needed(reply),
        "age_gate_count": int(user.get("age_gate_count") or 0),
        "delay": get_delay(intent, client_type),
    }
