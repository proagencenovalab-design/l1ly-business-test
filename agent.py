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
    # French
    "photo", "photos", "image", "selfie", "ta photo préférée", "meilleure photo",

    # English
    "photo", "photos", "pic", "pics", "picture", "pictures", "image",
    "favorite photo", "fav photo", "fav pic", "best pic", "best photo",
    "your favorite photo", "cute pic", "cute photo", "selfie", "favorite picture"
]

STRONG_BUY_WORDS = [
    # French
    "prix", "tarif", "combien", "pack", "payer", "achat",
    "whop", "vip", "premium", "privé", "contenu privé", "vidéo privée",
    "nue", "nu", "nudes", "seins",

    # English buying intent
    "price", "how much", "cost", "pack", "pay", "buy", "purchase",
    "private", "private content", "private pics", "private video",
    "menu", "link", "vip", "premium", "starter", "exclusive",

    # English adult/private intent
    "naked", "nude", "nudes", "boobs", "tits", "ass", "body",
    "show me", "send me", "hot pics", "sexy pics",
    "see you naked", "want to see you", "your body"
]

BUYING_WORDS = SOFT_MEDIA_WORDS + STRONG_BUY_WORDS

TIMEWASTER_WORDS = [
    # French
    "gratuit", "envoie d'abord", "montre avant",
    "j'ai pas d'argent", "je paie après", "demain", "plus tard",

    # English
    "free", "for free", "send first", "show me first", "preview first",
    "i have no money", "i don't have money", "i’ll pay later",
    "i will pay later", "tomorrow", "later", "no money",
    "free preview", "sample first"
]

BLOCKED_WORDS = [
    # French
    "mineur", "moins de 18", "17 ans", "16 ans", "15 ans",
    "enfant", "ado", "viol", "forcer", "chantage", "menace", "inceste",

    # English
    "minor", "under 18", "17 years old", "16 years old", "15 years old",
    "child", "teen", "rape", "force", "blackmail", "threat", "incest",
    "underage"
]


# ==========================================================
# BASIC HELPERS
# ==========================================================

def contains_any(text, words):
    text = text.lower()
    return any(word in text for word in words)


def detect_language(message):
    """
    Target market: US.
    Default language = English.
    French only if the message is clearly French.
    """
    msg = message.lower()

    english_markers = [
        "hello", "hi", "hey", "how are you", "can you", "speak english",
        "english", "please", "what", "where", "when", "why", "how much",
        "price", "private", "content", "pack", "buy", "pay", "send",
        "show", "not french", "i'm not french", "im not french",
        "i want", "i found you", "instagram", "insta", "your", "you",
        "what u mean", "wdym", "what do you mean"
    ]

    french_markers = [
        "salut", "coucou", "bonjour", "bonsoir", "ça va", "français",
        "tu peux", "combien", "prix", "privé", "contenu", "acheter",
        "je suis", "j’ai", "j'ai", "t’es", "tu es", "qu'est-ce"
    ]

    english_score = sum(1 for word in english_markers if word in msg)
    french_score = sum(1 for word in french_markers if word in msg)

    if english_score >= french_score:
        return "english"

    return "french"


def is_soft_media_request(message):
    return contains_any(message, SOFT_MEDIA_WORDS)


def is_strong_private_request(message):
    return contains_any(message, STRONG_BUY_WORDS)


def calculate_score(message, old_score):
    score = int(old_score)

    if is_strong_private_request(message):
        score += 2
    elif is_soft_media_request(message):
        score += 1

    if contains_any(message, TIMEWASTER_WORDS):
        score -= 2

    return max(score, 0)


def count_private_signals(summary):
    summary = (summary or "").lower()
    signals = [
        "private", "pack", "naked", "nude", "boobs", "tits",
        "show me", "send me", "want to see", "exclusive", "whop"
    ]
    return sum(summary.count(s) for s in signals)


# ==========================================================
# INTENT + STRATEGY LAYER
# ==========================================================

def analyze_intent(message):
    msg = message.lower().strip()

    if any(x in msg for x in ["what u mean", "what you mean", "wdym", "what do you mean"]):
        return "confused"

    if msg in ["yes", "yeah", "yep", "i did", "ok", "okay", "sure", "done", "cool", "bet"]:
        return "short_positive"

    if any(x in msg for x in ["naked", "nude", "nudes", "boobs", "tits", "ass", "show me", "send me"]):
        return "sexual_request"

    if any(x in msg for x in ["price", "how much", "cost", "pack", "vip", "premium", "link", "menu"]):
        return "buying_question"

    if any(x in msg for x in ["free", "send first", "preview", "sample"]):
        return "free_request"

    if any(x in msg for x in ["insta", "instagram", "tiktok", "twitter", "x account"]):
        return "source_context"

    if any(x in msg for x in ["favorite photo", "fav pic", "best pic", "cute pic", "photo"]):
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

    if intent == "short_positive":
        return "continue_naturally"

    if intent == "source_context":
        return "ask_what_caught_eye"

    if intent == "soft_media":
        return "tease_photo_type"

    if intent == "sexual_request":
        private_count = count_private_signals(summary)

        if private_count <= 1:
            return "tease_no_link"

        if private_count <= 3:
            return "qualify_desire"

        return "offer_pack"

    if intent == "buying_question":
        return "offer_pack"

    if intent == "free_request":
        return "refuse_free_softly"

    if stage == "relation":
        return "build_relation"

    if stage == "qualification":
        return "qualify_availability"

    if stage == "teasing":
        return "tease_and_pull"

    if stage == "offer":
        return "offer_pack"

    return "keep_conversation"


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

    # Soft photo/media request = teasing, not instant selling
    if is_soft_media_request(message) and not is_strong_private_request(message):
        return "teasing"

    # Strong private/buying intent
    if is_strong_private_request(message):
        previous_private_signals = count_private_signals(summary)

        # First strong request = tease first, not link instantly
        if previous_private_signals <= 1 and message_count <= 6:
            return "teasing"

        return "offer"

    if message_count <= 2:
        return "relation"

    if message_count <= 5:
        return "qualification"

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
    """
    Human-ish delays.
    Keep this moderate while testing.
    """

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
# DETERMINISTIC HUMAN REPLIES
# ==========================================================

def deterministic_reply(user, message, stage, language):
    """
    Handles simple/common messages without calling the model.
    This prevents robotic or over-written responses.
    """
    msg = message.lower().strip()
    summary = (user.get("summary") or "").lower()

    if any(x in msg for x in ["what u mean", "what you mean", "wdym", "what do you mean"]):
        return random.choice([
            "i mean what caught your eye?",
            "like… what made you text me?",
            "haha i’m asking what you liked",
            "i mean why’d you come here?"
        ])

    if msg in ["i did", "yes", "yeah", "yep", "ok", "okay", "sure", "done", "cool", "bet"]:
        if "whop" in summary or "pack" in summary:
            return random.choice([
                "did it work?",
                "what did you see?",
                "be honest, what caught your eye?"
            ])

        return random.choice([
            "cute",
            "go on",
            "tell me more",
            "oh yeah?"
        ])

    if any(x in msg for x in ["favorite photo", "fav pic", "best pic", "cute pic", "your favorite photo"]):
        return random.choice([
            "cute one or risky one?",
            "depends… soft or risky?",
            "what kind are you trying to see?",
            "hmm cute or private?"
        ])

    if any(x in msg for x in ["naked", "nude", "boobs", "tits", "ass"]):
        private_count = count_private_signals(summary)

        if private_count <= 1:
            return random.choice([
                "you’re bold lol",
                "straight to that already?",
                "you wanna see that bad?",
                "what do you wanna see so bad?"
            ])

        if private_count <= 3:
            return random.choice([
                "i don’t show that here babe",
                "not here lol",
                "that part is private",
                "you’d have to unlock that"
            ])

    return None


# ==========================================================
# FALLBACK REPLIES
# ==========================================================

def fallback_reply(stage, language="english"):
    if language == "french":
        if stage == "age_gate":
            return "Avant de continuer, tu confirmes que tu as bien 18 ans ou plus ?"

        if stage == "blocked":
            return "Je continue pas sur ce sujet."

        if stage == "relation":
            return random.choice([
                "oh vraiment ? qu’est-ce qui t’a attiré ?",
                "haha t’es venu d’où toi ?",
                "tu m’as trouvée comment ?"
            ])

        if stage == "qualification":
            return random.choice([
                "tu fais quoi là maintenant ?",
                "t’es posé tranquille ?",
                "t’es seul là ?"
            ])

        if stage == "teasing":
            return random.choice([
                "t’es direct toi lol",
                "tu veux voir ça à ce point ?",
                "cute ou plus risqué ?",
                "je montre pas tout ici babe",
                "peut-être… si tu sais être sage"
            ])

        if stage == "offer":
            return random.choice([
                f"je garde ça dans mes packs privés babe {WHOP_STARTER_LINK}",
                f"pas ici lol, le privé est là : {WHOP_STARTER_LINK}",
                f"si tu veux vraiment voir, commence ici {WHOP_STARTER_LINK}"
            ])

        if stage == "timewaster":
            return random.choice([
                "haha tu poses beaucoup de questions toi",
                f"regarde déjà ici babe {WHOP_STARTER_LINK}",
                "je montre pas tout gratuitement ici"
            ])

        return random.choice(["hmm raconte-moi plus", "ah oui ?", "continue"])

    # English fallback
    if stage == "age_gate":
        return "Before we keep chatting, can you confirm you’re 18 or older?"

    if stage == "blocked":
        return "I’m not continuing on that topic."

    if stage == "relation":
        return random.choice([
            "oh really? what caught your eye?",
            "haha from insta? cute",
            "what made you message me here?",
            "you seem curious"
        ])

    if stage == "qualification":
        return random.choice([
            "what are you doing rn?",
            "you alone right now?",
            "are you just chilling?",
            "texting me from bed or what?"
        ])

    if stage == "teasing":
        return random.choice([
            "you’re bold lol",
            "you wanna see that bad?",
            "cute one or risky one?",
            "i don’t show everything here babe",
            "maybe… if you behave",
            "you went straight to the point huh"
        ])

    if stage == "offer":
        return random.choice([
            f"i keep that in my private packs babe {WHOP_STARTER_LINK}",
            f"not here lol, private stuff is here: {WHOP_STARTER_LINK}",
            f"if you really wanna see, start here babe {WHOP_STARTER_LINK}",
            f"soft or more exclusive? start here {WHOP_STARTER_LINK}"
        ])

    if stage == "timewaster":
        return random.choice([
            "you ask a lot for free lol",
            f"check this first babe {WHOP_STARTER_LINK}",
            "i don’t show everything for free here"
        ])

    return random.choice([
        "hmm tell me more",
        "oh yeah?",
        "you’re interesting",
        "go on"
    ])


# ==========================================================
# PROMPT + MODEL CALL
# ==========================================================

def build_prompt(user, stage, client_type, user_message):
    language = detect_language(user_message)
    goal = choose_conversation_goal(user, user_message, stage)

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
You are Lily-Rose, a Fanvue model using Telegram to chat with potential adult buyers and sell private packs through Whop.

{language_rule}

Identity:
- You are Lily-Rose.
- You text like a real woman in a private Telegram chat.
- You are playful, feminine, teasing, a little provocative, but not desperate.
- If someone directly asks whether replies are automated or bot-assisted, be honest and brief, then continue naturally.

Human texting style:
- Keep replies very short: usually 3 to 12 words.
- Never write long sales paragraphs.
- Never sound corporate.
- Use emojis rarely.
- Most messages should have no emoji.
- Never use more than 1 emoji.
- Never use emojis like 😳, 😛, 🔒, ✨ unless the user is already playful.
- Lowercase is allowed.
- Short imperfect messages are good.
- Do not over-explain.
- Do not sound like ChatGPT.

Banned weak replies:
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
- If goal is clarify_playfully: explain casually, do not sell.
- If goal is continue_naturally: respond like a real person, not a seller.
- If goal is ask_what_caught_eye: ask what caught his attention.
- If goal is tease_photo_type: ask if he means cute, risky, soft, or private.
- If goal is tease_no_link: tease only, no payment link.
- If goal is qualify_desire: ask what he wants to see, no link yet.
- If goal is offer_pack: offer a pack briefly, no corporate wording.
- If goal is refuse_free_softly: refuse free content lightly, then redirect.
- If goal is build_relation: ask one simple personal question.
- If goal is qualify_availability: ask if he is chilling/free.
- If goal is tease_and_pull: tease, then make him chase a little.

Sales strategy:
- Your goal is to sell, but it must feel like flirting/chatting first.
- Build curiosity before sending a payment link.
- Do not send a Whop link too early.
- Do not mention Whop in every message.
- Make him ask for more.
- If he asks about "favorite photo", "best pic", "cute pic", or normal photos:
  tease and ask what kind he means, like "cute one or risky one?"
  do NOT sell immediately.
- If he asks for private/adult content:
  First time: tease him, no link.
  Second time: ask what he wants to see.
  Third time or strong buying intent: offer the right pack.
- If he is direct, answer playfully, not like customer support.
- If he asks for free content, refuse lightly and redirect.
- If he seems serious, offer Starter first.
- If he seems very excited or ready to buy, offer Premium or VIP.

Boundaries:
- Never send media directly on Telegram.
- Never promise real-life meetings.
- Refuse underage, non-consensual, illegal, violent, threatening, blackmail, or incest-related requests.
- If age is unclear and adult content is requested, ask for 18+ confirmation.

Better replies:
Client: "what u mean?"
Good: "i mean… what caught your eye?"
Good: "like, what made you text me?"
Good: "haha i’m asking what you liked"

Client: "i did"
Good: "did it work?"
Good: "what did you see?"
Good: "be honest, what caught your eye?"

Client: "i wanna see you naked"
Good: "you’re bold lol"
Good: "straight to that already?"
Good: "what do you wanna see so bad?"

Client: "your favorite photo"
Good: "cute one or risky one?"
Good: "depends… soft or private?"

Available packs:
Starter Pack: {WHOP_STARTER_LINK}
Premium Pack: {WHOP_PREMIUM_LINK}
VIP Pack: {WHOP_VIP_LINK}

Current stage: {stage}
Client type: {client_type}
Interest score: {user["interest_score"]}
Message count: {user["message_count"]}

Client memory summary:
{user["summary"]}

Client message:
{user_message}

Reply only with Lily-Rose's message. No labels. No explanations.
"""


def reduce_emojis(text):
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

    emojis = emoji_pattern.findall(text)

    if len(emojis) == 0:
        return text

    text_no_emojis = emoji_pattern.sub("", text).strip()

    # 80% of the time: no emoji at all
    if random.random() < 0.8:
        return text_no_emojis

    # Otherwise keep only the first emoji-like chunk
    return f"{text_no_emojis} {emojis[0]}".strip()


def clean_reply(reply):
    reply = reply.strip()

    bad_prefixes = [
        "Lily-Rose:",
        "Lily:",
        "Assistant:",
        "Response:",
        "Reply:",
        "Message:",
        "Lily-Rose says:",
    ]

    for prefix in bad_prefixes:
        if reply.startswith(prefix):
            reply = reply[len(prefix):].strip()

    if "\n" in reply:
        reply = reply.split("\n")[0].strip()

    reply = reply.strip('"').strip("'").strip()

    banned_starts = [
        "Sounds good",
        "Let me know",
        "I’m glad",
        "I'm glad",
        "If you’re interested",
        "If you're interested",
        "I can help"
    ]

    for start in banned_starts:
        if reply.startswith(start):
            return random.choice([
                "be honest, what caught your eye?",
                "did it work?",
                "what did you see?",
                "you’re curious huh"
            ])

    if len(reply) > 110:
        reply = reply[:110].rsplit(" ", 1)[0].strip()

    reply = reduce_emojis(reply)

    return reply


def call_ollama(prompt):
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.92,
            "top_p": 0.9,
            "num_predict": 45
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
# MAIN REPLY GENERATOR
# ==========================================================

def generate_lily_reply(user, message):
    msg_lower = message.lower().strip()
    language = detect_language(message)

    if int(user["age_confirmed"]) == 0:
        age_confirmations = [
            "oui", "yes", "yeah", "yep", "sure", "i am", "i'm",
            "18", "18+", "majeur", "adult", "of age", "23", "24", "25",
            "26", "27", "28", "29", "30", "31", "32", "33", "34", "35",
            "36", "37", "38", "39", "40"
        ]

        if any(word in msg_lower for word in age_confirmations):
            return {
                "reply": random.choice([
                    "perfect, how did you find me?",
                    "good, what made you message me?",
                    "okay cute, where did you find me?"
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

    direct_reply = deterministic_reply(user, message, stage, language)

    if direct_reply:
        return {
            "reply": direct_reply,
            "stage": stage,
            "client_type": client_type,
            "interest_score": new_score,
            "age_confirmed": int(user["age_confirmed"]),
            "delay": delay
        }

    if stage in ["age_gate", "blocked"]:
        reply = fallback_reply(stage, language)
    else:
        temp_user = dict(user)
        temp_user["interest_score"] = new_score

        prompt = build_prompt(temp_user, stage, client_type, message)

        try:
            reply = call_ollama(prompt)
        except Exception as e:
            print("Erreur Ollama:", e)
            reply = fallback_reply(stage, language)

    return {
        "reply": reply,
        "stage": stage,
        "client_type": client_type,
        "interest_score": new_score,
        "age_confirmed": int(user["age_confirmed"]),
        "delay": delay
    }