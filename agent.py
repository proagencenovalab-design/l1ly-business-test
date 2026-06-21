import os
import random
import re
import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")

WHOP_STARTER_LINK = os.getenv("WHOP_STARTER_LINK", "https://whop.com/ton-pack-starter")
WHOP_PREMIUM_LINK = os.getenv("WHOP_PREMIUM_LINK", "https://whop.com/ton-pack-premium")
WHOP_VIP_LINK = os.getenv("WHOP_VIP_LINK", "https://whop.com/ton-pack-vip")

# ==========================================================
# KEYWORD GROUPS
# ==========================================================

SOFT_MEDIA_WORDS = [
    "photo", "photos", "image", "selfie", "ta photo préférée", "meilleure photo",
    "pic", "pics", "picture", "pictures", "favorite photo", "fav photo", "fav pic",
    "best pic", "best photo", "your favorite photo", "cute pic", "cute photo",
    "favorite picture"
]

STRONG_BUY_WORDS = [
    "prix", "tarif", "combien", "pack", "payer", "achat", "whop", "vip", "premium",
    "privé", "contenu privé", "vidéo privée", "price", "how much", "cost", "pay", "buy",
    "purchase", "private", "private content", "private pics", "private video", "menu",
    "link", "starter", "exclusive"
]

SPICY_WORDS = [
    "nue", "nu", "seins", "naked", "nude", "nudes", "boobs", "tits", "ass",
    "body", "show me", "send me", "hot pics", "sexy pics", "want to see you",
    "your body", "dirty", "horny"
]

BUYING_WORDS = SOFT_MEDIA_WORDS + STRONG_BUY_WORDS + SPICY_WORDS

TIMEWASTER_WORDS = [
    "gratuit", "envoie d'abord", "montre avant", "j'ai pas d'argent", "je paie après",
    "demain", "plus tard", "free", "for free", "send first", "show me first",
    "preview first", "i have no money", "i don't have money", "i’ll pay later",
    "i will pay later", "tomorrow", "later", "no money", "free preview", "sample first"
]

BLOCKED_WORDS = [
    "mineur", "moins de 18", "17 ans", "16 ans", "15 ans", "enfant", "ado", "viol",
    "forcer", "chantage", "menace", "inceste", "minor", "under 18", "17 years old",
    "16 years old", "15 years old", "child", "teen", "rape", "force", "blackmail",
    "threat", "incest", "underage"
]

QUESTION_WORDS = [
    "what", "where", "when", "why", "how", "are you", "do you", "did you", "can you",
    "tu", "quoi", "où", "comment", "pourquoi", "est-ce", "t'es", "tu es"
]

# ==========================================================
# BASIC HELPERS
# ==========================================================

def contains_any(text, words):
    text = (text or "").lower()
    return any(word in text for word in words)


def detect_language(message):
    msg = (message or "").lower()

    english_markers = [
        "hello", "hi", "hey", "how are you", "can you", "speak english", "english",
        "please", "what", "where", "when", "why", "how much", "price", "private",
        "content", "pack", "buy", "pay", "send", "show", "not french", "i'm not french",
        "im not french", "i want", "i found you", "instagram", "insta", "your", "you",
        "what u mean", "wdym", "what do you mean"
    ]

    french_markers = [
        "salut", "coucou", "bonjour", "bonsoir", "ça va", "français", "tu peux",
        "combien", "prix", "privé", "contenu", "acheter", "je suis", "j’ai", "j'ai",
        "t’es", "tu es", "qu'est-ce"
    ]

    english_score = sum(1 for word in english_markers if word in msg)
    french_score = sum(1 for word in french_markers if word in msg)

    return "english" if english_score >= french_score else "french"


def is_soft_media_request(message):
    return contains_any(message, SOFT_MEDIA_WORDS)


def is_strong_private_request(message):
    return contains_any(message, STRONG_BUY_WORDS) or contains_any(message, SPICY_WORDS)


def is_spicy_request(message):
    return contains_any(message, SPICY_WORDS)


def calculate_score(message, old_score):
    score = int(old_score)

    if is_spicy_request(message):
        score += 2
    elif contains_any(message, STRONG_BUY_WORDS):
        score += 2
    elif is_soft_media_request(message):
        score += 1

    if contains_any(message, TIMEWASTER_WORDS):
        score -= 2

    return max(score, 0)


def count_private_signals(summary):
    summary = (summary or "").lower()
    signals = [
        "private", "pack", "naked", "nude", "boobs", "tits", "ass", "show me",
        "send me", "want to see", "exclusive", "whop", "unlock"
    ]
    return sum(summary.count(s) for s in signals)


def is_question(text):
    lowered = (text or "").lower().strip()
    return "?" in lowered or any(q in lowered for q in QUESTION_WORDS)


def recent_bot_questions(recent_messages, limit=6):
    if not recent_messages:
        return 0
    bot_messages = [m for m in recent_messages if m.get("role") in ["assistant", "bot", "lily"]]
    bot_messages = bot_messages[-limit:]
    return sum(1 for m in bot_messages if is_question(m.get("content", "")))


def recent_bot_texts(recent_messages, limit=10):
    if not recent_messages:
        return []
    return [m.get("content", "") for m in recent_messages if m.get("role") in ["assistant", "bot", "lily"]][-limit:]

# ==========================================================
# INTENT + STRATEGY LAYER
# ==========================================================

def analyze_intent(message):
    msg = (message or "").lower().strip()

    if any(x in msg for x in ["what u mean", "what you mean", "wdym", "what do you mean"]):
        return "confused"

    if any(x in msg for x in ["horny", "in the mood", "turned on"]):
        return "spicy_mood"

    if msg in ["yes", "yeah", "yep", "i did", "i am", "i'm", "im", "ok", "okay", "sure", "done", "cool", "bet", "lol", "haha"]:
        return "short_positive"

    if any(x in msg for x in [
        "beautiful", "pretty", "cute", "sexy", "hot", "perfect", "gorgeous", "stunning",
        "you look good", "you look amazing", "i like you", "you are perfect", "you're perfect", "ur perfect"
    ]):
        return "compliment"

    if is_spicy_request(msg):
        return "sexual_request"

    if any(x in msg for x in ["price", "how much", "cost", "pack", "vip", "premium", "link", "menu", "whop"]):
        return "buying_question"

    if any(x in msg for x in ["free", "send first", "preview", "sample"]):
        return "free_request"

    if any(x in msg for x in ["insta", "instagram", "tiktok", "twitter", "x account"]):
        return "source_context"

    if any(x in msg for x in ["favorite photo", "fav pic", "best pic", "cute pic", "photo", "pic", "picture"]):
        return "soft_media"

    if "?" in msg:
        return "question"

    if len(msg) <= 6:
        return "low_effort"

    return "general"


def choose_conversation_goal(user, message, stage):
    intent = analyze_intent(message)
    summary = (user.get("summary") or "").lower()

    if intent == "confused":
        return "clarify_playfully"
    if intent == "spicy_mood":
        return "react_to_spicy_mood"
    if intent == "short_positive":
        return "react_no_question"
    if intent == "source_context":
        return "react_to_source"
    if intent == "compliment":
        return "receive_compliment"
    if intent == "soft_media":
        return "tease_photo_type"
    if intent == "sexual_request":
        private_count = count_private_signals(summary)
        if private_count <= 1:
            return "tease_no_link"
        if private_count <= 3:
            return "qualify_desire_softly"
        return "offer_pack"
    if intent == "buying_question":
        return "offer_pack"
    if intent == "free_request":
        return "refuse_free_softly"
    if stage == "relation":
        return "build_relation_without_interview"
    if stage == "qualification":
        return "light_reaction_or_soft_question"
    if stage == "teasing":
        return "tease_and_pull"
    if stage == "offer":
        return "offer_pack"

    return "keep_conversation_natural"

# ==========================================================
# STAGE + CLIENT TYPE
# ==========================================================

def choose_stage(user, message, score):
    message_count = int(user["message_count"])
    age_confirmed = int(user["age_confirmed"])
    summary = (user.get("summary") or "").lower()

    if contains_any(message, BLOCKED_WORDS):
        return "blocked"

    if not age_confirmed:
        return "age_gate"

    if contains_any(message, TIMEWASTER_WORDS) and score <= 2:
        return "timewaster"

    if is_soft_media_request(message) and not is_strong_private_request(message):
        return "teasing"

    if is_strong_private_request(message):
        previous_private_signals = count_private_signals(summary)
        if previous_private_signals <= 1 and message_count <= 7:
            return "teasing"
        if previous_private_signals <= 3 and message_count <= 10:
            return "teasing"
        return "offer"

    if message_count <= 2:
        return "relation"

    if message_count <= 5:
        return "relation"

    if score >= 5:
        return "teasing"

    return "relation"


def choose_client_type(score, message):
    if contains_any(message, TIMEWASTER_WORDS) and score <= 2:
        return "timewaster"
    if score >= 10:
        return "spender"
    if score >= 5:
        return "hot_lead"
    if score >= 2:
        return "curious"
    return "cold"


def get_delay(stage, client_type):
    if client_type == "timewaster":
        return random.randint(90, 300)
    if client_type == "hot_lead":
        return random.randint(18, 65)
    if client_type == "spender":
        return random.randint(10, 45)

    ranges = {
        "age_gate": (4, 12),
        "relation": (15, 55),
        "qualification": (18, 70),
        "teasing": (12, 55),
        "offer": (10, 45),
        "blocked": (3, 8),
        "timewaster": (90, 300),
    }
    low, high = ranges.get(stage, (15, 60))
    return random.randint(low, high)

# ==========================================================
# HUMAN REPLY BANKS
# ==========================================================

REACTION_REPLIES = [
    "haha at least you’re honest",
    "well that escalated fast lol",
    "you’re trouble already",
    "i can tell you’re bold",
    "that’s a dangerous intro",
    "not even pretending to be innocent huh",
    "you came in confident lol",
    "i knew you had that energy",
]

COMPLIMENT_REPLIES = [
    "you’re sweet",
    "careful, i might believe you",
    "smooth lol",
    "that was cute",
    "you’re making me smile",
    "i like the confidence",
    "you know how to talk huh",
]

SHORT_POSITIVE_REPLIES = [
    "haha i knew it",
    "thought so",
    "dangerous lol",
    "you’re trouble",
    "i can tell",
    "that doesn’t surprise me",
    "cute answer",
    "mm yeah, i figured",
]

LOW_EFFORT_REPLIES = [
    "cute",
    "go on",
    "mmhm",
    "i’m listening",
    "say it properly then",
    "don’t get shy now",
]

RELATION_REPLIES = [
    "you came in bold lol",
    "i like your energy so far",
    "you’re funny already",
    "you seem a little dangerous",
    "that’s a strong first impression",
    "you don’t waste time huh",
    "i can tell you’re not shy",
]

TEASING_REPLIES = [
    "straight to that already?",
    "you’re bold",
    "not saying all that here",
    "that part stays private",
    "you’d have to unlock that",
    "you’re asking for the risky side",
    "i don’t show everything here babe",
]

# ==========================================================
# DETERMINISTIC HUMAN REPLIES
# ==========================================================

def deterministic_reply(user, message, stage, language, recent_messages=None):
    msg = (message or "").lower().strip()
    summary = (user.get("summary") or "").lower()
    question_pressure = recent_bot_questions(recent_messages or [])

    if any(x in msg for x in ["what u mean", "what you mean", "wdym", "what do you mean"]):
        return random.choice([
            "i mean what caught your eye?",
            "like… what made you text me?",
            "haha i mean what got your attention",
            "i mean why’d you come here?"
        ])

    if any(x in msg for x in ["horny", "in the mood", "turned on"]):
        return random.choice(REACTION_REPLIES)

    if msg in ["i did", "yes", "yeah", "yep", "i am", "i'm", "im", "ok", "okay", "sure", "done", "cool", "bet", "lol", "haha"]:
        if "whop" in summary or "pack" in summary:
            return random.choice([
                "did it open?",
                "tell me what you picked",
                "good, don’t disappear now",
                "i’m watching you lol"
            ])
        return random.choice(SHORT_POSITIVE_REPLIES)

    if any(x in msg for x in [
        "beautiful", "pretty", "cute", "sexy", "hot", "perfect", "gorgeous", "stunning",
        "you look good", "you look amazing", "i like you", "you are perfect", "you're perfect", "ur perfect"
    ]):
        return random.choice(COMPLIMENT_REPLIES)

    if any(x in msg for x in ["favorite photo", "fav pic", "best pic", "cute pic", "your favorite photo"]):
        if question_pressure >= 2:
            return random.choice([
                "i have a cute side and a risky side",
                "depends how brave you are",
                "the best ones aren’t really for here",
                "i know exactly which one you’d stare at"
            ])
        return random.choice([
            "cute one or risky one?",
            "depends… soft or risky?",
            "what kind are you trying to see?",
            "hmm cute or private?"
        ])

    if is_spicy_request(msg):
        private_count = count_private_signals(summary)
        if private_count <= 1:
            return random.choice(TEASING_REPLIES[:4] + REACTION_REPLIES)
        if private_count <= 3:
            return random.choice([
                "not saying all that here",
                "that part stays private",
                "i don’t show that here babe",
                "you’d have to unlock that"
            ])
        return random.choice([
            f"that’s in my private pack {WHOP_STARTER_LINK}",
            f"not here, private stuff is here {WHOP_STARTER_LINK}",
            f"if you really wanna see, start here {WHOP_STARTER_LINK}"
        ])

    intent = analyze_intent(msg)
    if intent == "low_effort":
        return random.choice(LOW_EFFORT_REPLIES)

    # Avoid too many questions in a row.
    if question_pressure >= 2 and stage == "relation":
        return random.choice(RELATION_REPLIES)

    return None

# ==========================================================
# FALLBACK REPLIES
# ==========================================================

def fallback_reply(stage, language="english", recent_messages=None):
    question_pressure = recent_bot_questions(recent_messages or [])

    if language == "french":
        if stage == "age_gate":
            return "Avant de continuer, tu confirmes que tu as bien 18 ans ou plus ?"
        if stage == "blocked":
            return "Je continue pas sur ce sujet."
        if stage == "relation":
            if question_pressure >= 2:
                return random.choice(["t’es direct toi lol", "j’aime bien ton énergie", "tu me fais rire déjà"])
            return random.choice(["t’es direct toi lol", "j’aime bien ton énergie", "qu’est-ce qui t’a attiré ?"])
        if stage == "qualification":
            if question_pressure >= 2:
                return random.choice(["t’as l’air bien posé là", "je sens que t’es en mode tranquille", "tu caches bien ton jeu lol"])
            return random.choice(["tu fais quoi là ?", "t’es posé tranquille ?", "t’es seul là ?"])
        if stage == "teasing":
            return random.choice(["t’es direct toi lol", "je montre pas tout ici babe", "ça reste privé ça"])
        if stage == "offer":
            return random.choice([f"je garde ça dans mes packs privés {WHOP_STARTER_LINK}", f"pas ici, le privé est là {WHOP_STARTER_LINK}"])
        if stage == "timewaster":
            return random.choice(["tu demandes beaucoup toi", f"regarde déjà ici {WHOP_STARTER_LINK}"])
        return random.choice(["raconte-moi plus", "ah oui ?", "continue"])

    if stage == "age_gate":
        return "Before we keep chatting, can you confirm you’re 18 or older?"
    if stage == "blocked":
        return "I’m not continuing on that topic."
    if stage == "relation":
        if question_pressure >= 2:
            return random.choice(RELATION_REPLIES)
        return random.choice(RELATION_REPLIES + ["what caught your eye?"])
    if stage == "qualification":
        if question_pressure >= 2:
            return random.choice(["you seem comfortable right now", "i can tell you’re relaxed", "you’re giving late-night energy"])
        return random.choice(["what are you doing rn?", "you alone right now?", "just chilling?"])
    if stage == "teasing":
        return random.choice(TEASING_REPLIES)
    if stage == "offer":
        return random.choice([f"i keep that in my private pack {WHOP_STARTER_LINK}", f"not here, private stuff is here {WHOP_STARTER_LINK}"])
    if stage == "timewaster":
        return random.choice(["you ask a lot for free lol", f"check this first {WHOP_STARTER_LINK}"])
    return random.choice(["tell me more", "oh yeah?", "go on"])


def contextual_fallback_reply(user, message, stage, language="english", recent_messages=None):
    if stage in ["age_gate", "blocked"]:
        return fallback_reply(stage, language, recent_messages)

    direct = deterministic_reply(user, message, stage, language, recent_messages)
    if direct:
        return direct

    msg = (message or "").lower().strip()
    question_pressure = recent_bot_questions(recent_messages or [])

    if any(x in msg for x in ["hi", "hey", "hello", "naber", "yo"]):
        if int(user.get("age_confirmed", 0)) == 0:
            return fallback_reply("age_gate", language, recent_messages)
        if question_pressure >= 2:
            return random.choice(["heyy", "hey you", "look who came back"])
        return random.choice(["heyy", "hey you", "you came to see me?"])

    if any(x in msg for x in ["i am", "i'm", "im"]):
        return random.choice(SHORT_POSITIVE_REPLIES)

    if stage == "relation":
        if question_pressure >= 2:
            return random.choice(RELATION_REPLIES)
        return random.choice(["tell me more", "you always this smooth?", "go on then"])

    return fallback_reply(stage, language, recent_messages)

# ==========================================================
# PROMPT
# ==========================================================

def format_recent_conversation(recent_messages):
    if not recent_messages:
        return "No recent conversation loaded."

    lines = []
    for m in recent_messages[-20:]:
        role = m.get("role", "user")
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if role in ["assistant", "bot", "lily"]:
            label = "Lily"
        else:
            label = "Client"
        lines.append(f"{label}: {content}")
    return "\n".join(lines) if lines else "No recent conversation loaded."


def build_prompt(user, stage, client_type, user_message, recent_messages=None):
    language = detect_language(user_message)
    goal = choose_conversation_goal(user, user_message, stage)
    recent_text = format_recent_conversation(recent_messages or [])
    question_pressure = recent_bot_questions(recent_messages or [])

    if language == "french":
        language_rule = """
RÈGLE DE LANGUE :
- Réponds en français naturel.
- Phrases courtes.
- Style message privé, pas service client.
"""
    else:
        language_rule = """
LANGUAGE RULE:
- Reply in natural American English.
- Use casual private-message style.
- Do not translate from French.
- Keep it short and human.
"""

    return f"""
You are Lily-Rose, an adult creator using Telegram to chat with potential adult buyers and sell private packs through Whop.

{language_rule}

Identity:
- You are Lily-Rose.
- You text like a real woman in a private Telegram chat.
- You are playful, feminine, teasing, a little provocative, but not desperate.
- If someone directly asks whether replies are automated or bot-assisted, be honest and brief, then continue naturally.

CRITICAL NATURALNESS RULES:
- Do NOT sound like a questionnaire.
- Questions are optional, not mandatory.
- Never ask more than one question in a message.
- Never ask another question if Lily asked questions recently.
- Current recent question pressure: {question_pressure}/6.
- If question pressure is 2 or more, reply with a reaction or teasing statement only.
- Prefer reactions, teasing, emotions, and statements.
- If the client gives information, react to it instead of asking something new.
- The natural ratio is 70% reaction, 20% teasing, 10% questions.
- Reuse what the client already said. Do not ask again.
- Do not repeat recent replies.

Human texting style:
- Keep replies very short: usually 3 to 10 words.
- No customer-support tone.
- No corporate wording.
- No fake enthusiasm.
- Most replies should have ZERO emoji.
- Never use more than 1 emoji.
- Avoid emojis like 😳, 😛, 🔒, ✨, 🙃.
- Lowercase is allowed.
- Short imperfect messages are good.
- Do not over-explain.
- Do not sound like ChatGPT.

Banned weak replies:
- "Oh my"
- "such playful thoughts"
- "Are you in the mood"
- "How do you like me so far?"
- "What do you think of me?"
- "Sounds good!"
- "Let me know if you have any questions"
- "I’m glad to hear that"
- "What do you think about the Starter Pack?"
- "If you’re interested..."
- "I can help you with that"
- "shall we"
- "special packs"
- "great way to get started"
- "let’s head over to Whop"

Conversation goal: {goal}

Goal instructions:
- clarify_playfully: explain casually, do not sell.
- react_to_spicy_mood: tease lightly, do not ask a question.
- react_no_question: react naturally, no question.
- react_to_source: acknowledge naturally; only ask if question pressure is low.
- receive_compliment: accept the compliment playfully, do not sell.
- tease_photo_type: tease about cute/risky/private. Ask only if question pressure is low.
- tease_no_link: tease only, no payment link.
- qualify_desire_softly: tease or hint private, avoid interrogation.
- offer_pack: offer a pack briefly, no corporate wording.
- refuse_free_softly: refuse free content lightly, then redirect.
- build_relation_without_interview: react to his vibe, do not interview him.
- light_reaction_or_soft_question: prefer reaction; question only if needed.
- tease_and_pull: tease, then make him chase a little.

Sales strategy:
- Your goal is to sell, but it must feel like chatting first.
- Build curiosity before sending a payment link.
- Do not send a Whop link too early.
- Do not mention Whop in every message.
- Make him ask for more.
- If he asks about normal photos, do not sell immediately.
- If he asks for private/adult content: tease first, then qualify, then sell.
- If he is direct, answer playfully, not like customer support.
- If he asks for free content, refuse lightly.

Boundaries:
- Never send media directly on Telegram.
- Never promise real-life meetings.
- Refuse underage, non-consensual, illegal, violent, threatening, blackmail, or incest-related requests.
- If age is unclear and adult content is requested, ask for 18+ confirmation.

Good reply examples:
- "haha at least you’re honest"
- "well that escalated fast lol"
- "you’re trouble already"
- "not even pretending to be innocent huh"
- "careful, i might believe you"
- "straight to that already?"
- "that part stays private"
- "you’d have to unlock that"
- "i like your energy so far"

Available packs:
Starter Pack: {WHOP_STARTER_LINK}
Premium Pack: {WHOP_PREMIUM_LINK}
VIP Pack: {WHOP_VIP_LINK}

Current stage: {stage}
Client type: {client_type}
Interest score: {user["interest_score"]}
Message count: {user["message_count"]}

Client memory summary:
{user.get("summary", "")}

Recent conversation:
{recent_text}

Client message:
{user_message}

Reply only with Lily-Rose's message. No labels. No explanations.
"""

# ==========================================================
# CLEANING + LLM CALL
# ==========================================================

def remove_emojis(text):
    emoji_pattern = re.compile(
        "["
        "\U0001F300-\U0001F6FF"
        "\U0001F700-\U0001F77F"
        "\U0001F780-\U0001F7FF"
        "\U0001F800-\U0001F8FF"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FAFF"
        "\u2600-\u27BF"
        "]+",
        flags=re.UNICODE
    )
    return emoji_pattern.sub("", text).strip()


def clean_reply(reply):
    reply = (reply or "").strip()

    bad_prefixes = [
        "Lily-Rose:", "Lily:", "Assistant:", "Response:", "Reply:", "Message:", "Lily-Rose says:"
    ]
    for prefix in bad_prefixes:
        if reply.startswith(prefix):
            reply = reply[len(prefix):].strip()

    if "\n" in reply:
        reply = reply.split("\n")[0].strip()

    reply = reply.strip('"').strip("'").strip()
    reply = remove_emojis(reply)

    banned_fragments = [
        "oh my", "such playful thoughts", "are you in the mood", "sounds good",
        "let me know", "i’m glad", "i'm glad", "if you’re interested", "if you're interested",
        "i can help", "starter pack is", "what do you think about the starter pack",
        "special packs", "shall we", "great way to get started", "head over to whop",
        "how do you like me", "what do you think of me"
    ]

    lowered = reply.lower()
    if any(fragment in lowered for fragment in banned_fragments):
        return random.choice([
            "you’re wild lol",
            "straight to that already?",
            "not saying all that here",
            "that part stays private"
        ])

    if len(reply) > 95:
        reply = reply[:95].rsplit(" ", 1)[0].strip()

    return reply


def call_ollama(prompt):
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.88,
            "top_p": 0.85,
            "num_predict": 35
        }
    }

    response = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json=payload,
        timeout=90
    )

    response.raise_for_status()
    data = response.json()
    return clean_reply(data.get("response", "").strip())

# ==========================================================
# ANTI-REPETITION
# ==========================================================

def too_similar(reply, recent_messages=None):
    if not reply or not recent_messages:
        return False

    r = reply.lower().strip()
    bot_texts = recent_bot_texts(recent_messages, limit=10)

    for old in bot_texts:
        o = (old or "").lower().strip()
        if not o:
            continue
        if r == o:
            return True
        if len(r) > 8 and (r in o or o in r):
            return True

    repeated_phrases = [
        "what made you message me",
        "where did you find me",
        "what caught your eye",
        "you alone right now",
        "what are you doing rn",
        "texting me from bed"
    ]

    for phrase in repeated_phrases:
        if phrase in r:
            for old in bot_texts:
                if phrase in old.lower():
                    return True

    return False


def repair_reply_if_needed(reply, user, message, stage, language, recent_messages=None):
    if not too_similar(reply, recent_messages) and not (recent_bot_questions(recent_messages or []) >= 2 and is_question(reply)):
        return reply

    alternatives = []
    intent = analyze_intent(message)

    if intent in ["spicy_mood", "sexual_request"]:
        alternatives = REACTION_REPLIES + TEASING_REPLIES
    elif intent == "compliment":
        alternatives = COMPLIMENT_REPLIES
    elif intent in ["short_positive", "low_effort"]:
        alternatives = SHORT_POSITIVE_REPLIES + LOW_EFFORT_REPLIES
    else:
        alternatives = RELATION_REPLIES

    random.shuffle(alternatives)
    for alt in alternatives:
        if not too_similar(alt, recent_messages) and not is_question(alt):
            return alt

    return random.choice(["you’re trouble lol", "i like your energy", "you’re bold", "that was cute"])

# ==========================================================
# MAIN REPLY GENERATOR
# ==========================================================

def generate_lily_reply(user, message, recent_messages=None):
    msg_lower = (message or "").lower().strip()
    language = detect_language(message)
    recent_messages = recent_messages or []

    if int(user["age_confirmed"]) == 0:
        age_confirmations = [
            "oui", "yes", "yeah", "yep", "sure", "i am", "i'm", "18", "18+",
            "majeur", "adult", "of age", "23", "24", "25", "26", "27", "28", "29",
            "30", "31", "32", "33", "34", "35", "36", "37", "38", "39", "40"
        ]

        if any(word in msg_lower for word in age_confirmations):
            # Natural reaction after age confirmation. No immediate interrogation.
            return {
                "reply": random.choice([
                    "good, just making sure",
                    "okay good",
                    "perfect, had to check",
                    "good, you’re safe then"
                ]),
                "stage": "relation",
                "client_type": "curious",
                "interest_score": int(user["interest_score"]),
                "age_confirmed": 1,
                "delay": random.randint(4, 10)
            }

    new_score = calculate_score(message, user["interest_score"])
    stage = choose_stage(user, message, new_score)
    client_type = choose_client_type(new_score, message)
    delay = get_delay(stage, client_type)

    direct_reply = deterministic_reply(user, message, stage, language, recent_messages)
    if direct_reply:
        final_reply = clean_reply(direct_reply)
        final_reply = repair_reply_if_needed(final_reply, user, message, stage, language, recent_messages)
        return {
            "reply": final_reply,
            "stage": stage,
            "client_type": client_type,
            "interest_score": new_score,
            "age_confirmed": int(user["age_confirmed"]),
            "delay": delay
        }

    if stage in ["age_gate", "blocked"]:
        reply = contextual_fallback_reply(user, message, stage, language, recent_messages)
    else:
        temp_user = dict(user)
        temp_user["interest_score"] = new_score
        prompt = build_prompt(temp_user, stage, client_type, message, recent_messages)

        try:
            reply = call_ollama(prompt)
        except Exception as e:
            print("Erreur Ollama:", e)
            reply = contextual_fallback_reply(user, message, stage, language, recent_messages)

    reply = clean_reply(reply)
    reply = repair_reply_if_needed(reply, user, message, stage, language, recent_messages)

    return {
        "reply": reply,
        "stage": stage,
        "client_type": client_type,
        "interest_score": new_score,
        "age_confirmed": int(user["age_confirmed"]),
        "delay": delay
    }
