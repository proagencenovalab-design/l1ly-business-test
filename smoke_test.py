from agent import generate_lily_reply

BASE = {
    "age_confirmed": 1,
    "interest_score": 0,
    "message_count": 2,
    "preferred_language": "french",
    "last_intent": "",
    "conversation_tone": "balanced",
}

TESTS = [
    "salut",
    "ça va et toi ?",
    "tu viens d'où ?",
    "tu es vraiment belle",
    "j'aimerais bien te voir nue",
    "combien coûte ton privé ?",
    "je comprends pas ce que tu veux dire",
    "parle moi uniquement en français",
]

for text in TESTS:
    result = generate_lily_reply(BASE.copy(), text, [])
    print(text, "=>", result)
