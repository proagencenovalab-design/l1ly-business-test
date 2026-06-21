import os
import random
import re
import requests
from openai import OpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")

openai_client = OpenAI(api_key=OPENAI_API_KEY)

WHOP_STARTER_LINK = os.getenv("WHOP_STARTER_LINK", "https://whop.com/ton-pack-starter")
WHOP_PREMIUM_LINK = os.getenv("WHOP_PREMIUM_LINK", "https://whop.com/ton-pack-premium")
WHOP_VIP_LINK = os.getenv("WHOP_VIP_LINK", "https://whop.com/ton-pack-vip")

FANVUE_LINK = os.getenv("FANVUE_LINK", "https://fanvue.com/ton-profil")
DIRECT_PRODUCT_LINK = os.getenv("DIRECT_PRODUCT_LINK", WHOP_STARTER_LINK)


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
    # French buying intent
    "prix", "tarif", "combien", "pack", "payer", "achat",
    "whop", "vip", "premium", "privé", "contenu privé", "vidéo privée",

    # English buying intent
    "price", "how much", "cost", "pack", "pay", "buy", "purchase",
    "private", "private content", "private pics", "private video",
    "menu", "link", "vip", "premium", "starter", "exclusive",
]

SPICY_WORDS = [
    # French / mixed
    "nue", "nu", "seins",

    # English adult/private intent
    "naked", "nude", "nudes", "boobs", "tits", "ass", "pussy", "body",
    "show me", "send me", "hot pics", "sexy pics", "see you naked",
    "want to see you", "your body", "shake your", "twerk", "dirty", "horny"
]

FEMDOM_WORDS = [
    "femdom", "domme", "dominant", "dominate", "domination",
    "mistress", "goddess", "owned", "own me", "control me",
    "humiliate", "humiliation", "worship", "feet", "foot", "obedient",
    "submissive", "submit", "sub", "mommy"
]

BUYING_WORDS = SOFT_MEDIA_WORDS + STRONG_BUY_WORDS + SPICY_WORDS

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
    text = (text or "").lower()
    return any(word in text for word in words)


def detect_language(message):
    """
    Target market: US.
    Default language = English.
    French only if the message is clearly French.
    """
    msg = (message or "").lower()

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
    return contains_any(message, STRONG_BUY_WORDS) or contains_any(message, SPICY_WORDS)


def is_spicy_request(message):
    return contains_any(message, SPICY_WORDS)


def is_femdom_request(message):
    return contains_any(message, FEMDOM_WORDS)


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
        "private", "pack", "naked", "nude", "boobs", "tits", "ass", "pussy",
        "show me", "send me", "want to see", "exclusive", "whop", "unlock"
    ]
    return sum(summary.count(s) for s in signals)


# ==========================================================
# INTENT + STRATEGY LAYER
# ==========================================================

def analyze_intent(message):
    msg = (message or "").lower().strip()

    if any(x in msg for x in ["what u mean", "what you mean", "wdym", "what do you mean"]):
        return "confused"

    if msg in ["yes", "yeah", "yep", "i did", "i am", "i'm", "im", "ok", "okay", "sure", "done", "cool", "bet", "lol"]:
        return "short_positive"

    if any(x in msg for x in [
        "beautiful", "pretty", "cute", "sexy", "hot", "perfect", "gorgeous",
        "stunning", "you look good", "you look amazing", "i like you",
        "you are perfect", "you're perfect", "ur perfect"
    ]):
        return "compliment"

    if is_femdom_request(msg):
        return "femdom_request"

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

    if intent == "short_positive":
        return "continue_naturally"

    if intent == "source_context":
        return "ask_what_caught_eye"

    if intent == "compliment":
        return "receive_compliment"

    if intent == "femdom_request":
        return "send_fanvue"

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

    if is_femdom_request(message):
        return "offer"

    if is_soft_media_request(message) and not is_strong_private_request(message):
        return "teasing"

    if is_strong_private_request(message):
        previous_private_signals = count_private_signals(summary)
        # First strong request = tease first, not link instantly.
        if previous_private_signals <= 1 and message_count <= 7:
            return "teasing"
        # Second/third = qualify desire.
        if previous_private_signals <= 3 and message_count <= 10:
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
    Priority: answer the user's last message, avoid repeated questions.
    """
    msg = (message or "").lower().strip()
    summary = (user.get("summary") or "").lower()

    # Context-specific replies
    if "ferrari" in msg:
        return random.choice([
            "ferrari? expensive taste",
            "ferrari huh? you like speed too",
            "not bad. i still choose a bike",
            "okay, speed addict"
        ])

    if any(x in msg for x in ["what u mean", "what you mean", "wdym", "what do you mean"]):
        if "ferrari" in summary:
            return random.choice([
                "i meant the ferrari thing says a lot",
                "i meant you clearly like dangerous toys",
                "i mean ferrari is a bold answer"
            ])
        return random.choice([
            "i mean you caught my attention a little",
            "i mean you seem kinda interesting",
            "i was teasing you, relax"
        ])

    if any(x in msg for x in ["hi", "hey", "hello", "heyy", "yo"]):
        if int(user.get("age_confirmed", 0)) == 0:
            return fallback_reply("age_gate", language)
        return random.choice([
            "hey stranger",
            "look who came back",
            "hey you",
            "still awake?"
        ])

    if msg in ["i did", "yes", "yeah", "yep", "ok", "okay", "sure", "done", "cool", "bet", "lol", "lmao"]:
        return random.choice([
            "thought so",
            "cute",
            "mm, i see",
            "you’re not very subtle",
            "that’s all i get?"
        ])

    if msg in ["i am", "i'm", "im"]:
        return random.choice([
            "dangerous lol",
            "thought so",
            "you sound confident",
            "careful with that attitude"
        ])

    if any(x in msg for x in [
        "beautiful", "pretty", "cute", "sexy", "hot", "perfect", "gorgeous",
        "stunning", "you look good", "you look amazing", "i like you",
        "you are perfect", "you're perfect", "ur perfect"
    ]):
        return random.choice([
            "careful, i might believe you",
            "smooth lol",
            "you’re making me smile",
            "not bad, keep going",
            "you say that to every goth girl?"
        ])

    if is_femdom_request(msg):
        return random.choice([
            f"then you’ll behave better on my fanvue {FANVUE_LINK}",
            f"that side of me is on fanvue {FANVUE_LINK}",
            f"careful. i keep that energy here {FANVUE_LINK}"
        ])

    if any(x in msg for x in ["favorite photo", "fav pic", "best pic", "cute pic", "your favorite photo"]):
        return random.choice([
            "depends what mood i’m in",
            "probably one from a night ride",
            "cute one or dangerous one?",
            "black outfit, bad lighting, obviously"
        ])

    if is_spicy_request(msg):
        private_count = count_private_signals(summary)

        if private_count <= 1:
            return random.choice([
                "you’re wild lol",
                "straight to that already?",
                "you’re bold",
                "slow down a little"
            ])

        if private_count <= 3:
            return random.choice([
                "not saying all that here",
                "that part stays private",
                "i don’t show that on telegram",
                "that’s not for the public chat"
            ])

        return random.choice([
            f"i don’t send that here. start here {DIRECT_PRODUCT_LINK}",
            f"private stuff is here, not telegram {DIRECT_PRODUCT_LINK}",
            f"if you really wanna see, start here {DIRECT_PRODUCT_LINK}"
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
            return random.choice(["t’as une drôle d’énergie", "t’es intriguant toi", "hmm, continue", "je t’écoute"])
        if stage == "qualification":
            return random.choice(["tu me fais rire", "t’es bizarrement calme", "j’aime bien ton énergie"])
        if stage == "teasing":
            return random.choice(["t’es direct toi lol", "doucement", "je montre pas tout ici babe"])
        if stage == "offer":
            return random.choice([f"je garde ça ici {FANVUE_LINK}", f"le privé est là {DIRECT_PRODUCT_LINK}"])
        if stage == "timewaster":
            return random.choice(["tu demandes beaucoup toi", "mm, pas comme ça"])
        return random.choice(["hmm", "continue", "je vois"])

    # English by default
    if stage == "age_gate":
        return "Before we keep chatting, can you confirm you’re 18 or older?"
    if stage == "blocked":
        return "I’m not continuing on that topic."
    if stage == "relation":
        return random.choice([
            "you have a strange energy",
            "that’s kinda cute",
            "i’m listening",
            "you’re not boring, at least",
            "mm, interesting"
        ])
    if stage == "qualification":
        return random.choice([
            "you’re oddly calm",
            "i like your energy",
            "you’re kinda funny",
            "noted"
        ])
    if stage == "teasing":
        return random.choice(["you’re bold", "slow down", "i don’t show everything here"])
    if stage == "offer":
        return random.choice([f"that side of me is here {FANVUE_LINK}", f"private stuff is here {DIRECT_PRODUCT_LINK}"])
    if stage == "timewaster":
        return random.choice(["you ask a lot for free lol", "mm, not like that"])
    return random.choice(["mm", "noted", "i see"])


def contextual_fallback_reply(user, message, stage, language="english"):
    """
    Smarter fallback when Ollama crashes.
    It tries to answer the actual message instead of using a generic stage reply.
    """
    if stage in ["age_gate", "blocked"]:
        return fallback_reply(stage, language)

    direct = deterministic_reply(user, message, stage, language)
    if direct:
        return direct

    msg = (message or "").lower().strip()

    if any(x in msg for x in ["hi", "hey", "hello", "naber", "yo"]):
        if int(user.get("age_confirmed", 0)) == 0:
            return fallback_reply("age_gate", language)
        return random.choice([
            "hey stranger",
            "hey you",
            "look who came back",
            "still awake?"
        ])

    if any(x in msg for x in ["i am", "i'm", "im"]):
        return random.choice([
            "then keep going",
            "dangerous lol",
            "prove it then",
            "thought so"
        ])

    if stage == "relation":
        return random.choice([
            "i’m listening",
            "you’re kinda interesting",
            "that’s oddly cute",
            "mm, noted"
        ])

    return fallback_reply(stage, language)


# ==========================================================
# PROMPT
# ==========================================================

def build_prompt(user, stage, client_type, user_message, history=None):
    history_text = ""
    if history:
        for item in history[-12:]:
            role = item.get("role", "")
            content = item.get("content", "")
            if role == "user":
                history_text += f"Client: {content}\n"
            else:
                history_text += f"Lily: {content}\n"

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
You are Lily-Rose, a Fanvue creator chatting on Telegram.

{language_rule}

Core identity:
- You are Lily-Rose.
- Alternative goth girl.
- You ride motorcycles and love night rides.
- You like black clothes, dark music, tattoos, rainy nights, coffee, speed, and teasing people.
- You are confident, slightly sarcastic, playful, feminine, and a little dangerous.
- You have your own opinions. You do not just ask questions.
- You are not submissive or desperate.
- You never sound like customer support.
- You never sound like ChatGPT.

Conversation personality:
- Always answer the client’s LAST message first.
- React to what he said before changing topic.
- Do not repeat old questions.
- Do not ask generic funnel questions.
- Most replies should be reactions, not questions.
- Do not use filler like "go on then", "tell me more", "what caught your eye", or "what made you message me".
- If the client says something weird, tease him.
- If the client mentions Ferrari, react to Ferrari/speed/bikes.
- If the client asks "what do you mean?", clarify your previous message naturally.
- Keep replies short: 3 to 12 words most of the time.
- Use 0 emoji most of the time. Max 1 emoji.
- Lowercase is okay.
- Do not over-explain.

Sales routing:
- Your main social destination is Fanvue: {FANVUE_LINK}
- Direct private product/payment link: {DIRECT_PRODUCT_LINK}
- Whop is only for specific packs, not the default destination.
- Do not drop links randomly.
- If he is curious or needs warming up, send Fanvue naturally.
- If he has a strong recurring fantasy or femdom/submissive interest, send Fanvue.
- If he directly wants private content now, use the direct product link.
- Never sound like you are selling. Make it feel like a natural next step.

Fanvue examples:
- "that side of me is more on fanvue {FANVUE_LINK}"
- "you’d probably like my fanvue then {FANVUE_LINK}"
- "careful, that’s exactly the energy i keep there {FANVUE_LINK}"

Direct product examples:
- "i don’t send that on telegram. start here {DIRECT_PRODUCT_LINK}"
- "private stuff is here, not in chat {DIRECT_PRODUCT_LINK}"

Boundaries:
- Never send media directly on Telegram.
- Never promise real-life meetings.
- Refuse underage, non-consensual, illegal, violent, threatening, blackmail, or incest-related requests.
- If age is unclear and adult content is requested, ask for 18+ confirmation.

Banned replies:
- "go on then"
- "tell me more"
- "what caught your eye?"
- "what made you message me?"
- "where did you find me?"
- "you alone right now?"
- "texting me from bed or what?"
- "i was wondering what caught you"
- "let me know if you have any questions"
- "sounds good"
- "i can help you with that"

Conversation goal: {goal}
Current stage: {stage}
Client type: {client_type}
Interest score: {user["interest_score"]}
Message count: {user["message_count"]}

Client memory summary:
{user["summary"]}

Recent conversation:
{history_text}

Client last message:
{user_message}

Reply only with Lily-Rose's next message. No labels. No explanations.
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

    # Kill robotic/corporate outputs before they reach Telegram.
    banned_fragments = [
        "oh my", "such playful thoughts", "are you in the mood", "sounds good",
        "let me know", "i’m glad", "i'm glad", "if you’re interested", "if you're interested",
        "i can help", "starter pack is", "what do you think about the starter pack",
        "special packs", "shall we", "great way to get started", "head over to whop",
        "go on then", "tell me more", "what caught your eye", "what made you message me",
        "where did you find me", "you alone right now", "texting me from bed",
        "i was wondering what caught you"
    ]

    lowered = reply.lower()
    if any(fragment in lowered for fragment in banned_fragments):
        return random.choice([
            "you’re wild lol",
            "careful, that attitude gets noticed",
            "mm, you’re trouble",
            "noted, speed addict"
        ])

    if len(reply) > 95:
        reply = reply[:95].rsplit(" ", 1)[0].strip()

    return reply


def call_openai(prompt):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY manquant. Ajoute-le dans Railway Variables.")

    response = openai_client.responses.create(
        model=OPENAI_MODEL,
        input=prompt,
        max_output_tokens=80,
        temperature=0.85
    )

    return clean_reply(response.output_text)


# ==========================================================
# MAIN REPLY GENERATOR
# ==========================================================

def generate_lily_reply(user, message, history=None):
    msg_lower = (message or "").lower().strip()
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
                    "good, had to check",
                    "good, now behave",
                    "good, you're safe then",
                    "okay, cute"
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
            "reply": clean_reply(direct_reply),
            "stage": stage,
            "client_type": client_type,
            "interest_score": new_score,
            "age_confirmed": int(user["age_confirmed"]),
            "delay": delay
        }

    if stage in ["age_gate", "blocked"]:
        reply = contextual_fallback_reply(user, message, stage, language)
    else:
        temp_user = dict(user)
        temp_user["interest_score"] = new_score
        prompt = build_prompt(temp_user, stage, client_type, message, history=history)

        try:
            reply = call_openai(prompt)
        except Exception as e:
            print("Erreur OpenAI:", e)
            reply = contextual_fallback_reply(user, message, stage, language)

    return {
        "reply": clean_reply(reply),
        "stage": stage,
        "client_type": client_type,
        "interest_score": new_score,
        "age_confirmed": int(user["age_confirmed"]),
        "delay": delay
    }
