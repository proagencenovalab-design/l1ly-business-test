from agent import generate_lily_reply

BASE = {
    "age_confirmed": 1,
    "preferred_language": "",
    "interest_score": 0,
    "message_count": 2,
    "client_type": "cold",
    "summary": "",
}

CASES = [
    ("heyy", "how are"),
    ("i'm fine and u ?", "good"),
    ("where u from ?", "seattle"),
    ("est-ce qu'on peut continuer en français ?", "français"),
    ("i don't understand", "sorry"),
]

for message, expected in CASES:
    result = generate_lily_reply(dict(BASE), message, [])
    reply = result["reply"].lower()
    ok = expected in reply
    print("OK" if ok else "FAIL", "|", message, "->", result["reply"])
