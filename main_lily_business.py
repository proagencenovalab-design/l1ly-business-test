import os
import time
import requests

from memory import init_db, get_or_create_user, update_user, save_message, get_recent_messages
from agent import generate_lily_reply

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is missing. Add it in Railway Variables.")

def telegram_post(method, payload):
    response = requests.post(f"{API_BASE}/{method}", json=payload, timeout=30)
    try:
        data = response.json()
    except Exception:
        data = {"ok": False, "raw": response.text}
    return data

def get_updates(offset=None, timeout=50):
    params = {
        "timeout": timeout,
        "allowed_updates": ["business_message", "message", "business_connection"]
    }
    if offset is not None:
        params["offset"] = offset

    response = requests.get(f"{API_BASE}/getUpdates", params=params, timeout=timeout + 10)
    response.raise_for_status()
    return response.json()

def send_business_message(chat_id, text, business_connection_id):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "business_connection_id": business_connection_id,
        "disable_web_page_preview": True
    }
    return telegram_post("sendMessage", payload)

def handle_business_message(update):
    message = update.get("business_message")
    if not message:
        return

    text = message.get("text", "")
    if not text:
        return

    chat = message.get("chat", {})
    sender = message.get("from", {})
    chat_id = str(chat.get("id"))
    business_connection_id = message.get("business_connection_id")

    if not chat_id or not business_connection_id:
        return

    username = chat.get("username") or sender.get("username") or ""
    first_name = chat.get("first_name") or sender.get("first_name") or ""

    print("\n==============================", flush=True)
    print(f"Message reçu : {text}", flush=True)
    print(f"De : {username or first_name or chat_id}", flush=True)
    print("==============================", flush=True)

    user = get_or_create_user(
        chat_id=chat_id,
        username=username,
        first_name=first_name
    )

    # Sauvegarde le message client dans PostgreSQL.
    save_message(chat_id, "user", text)

    # Charge les 20 derniers messages pour éviter les répétitions
    # et permettre à Lily de reprendre le contexte naturellement.
    history = get_recent_messages(chat_id, limit=20)

    result = generate_lily_reply(user, text, history=history)

    print(f"Stage : {result['stage']}", flush=True)
    print(f"Type client : {result['client_type']}", flush=True)
    print(f"Score : {result['interest_score']}", flush=True)
    print(f"Âge confirmé : {result['age_confirmed']}", flush=True)
    print(f"Réponse dans {result['delay']} secondes", flush=True)
    print(f"Réponse : {result['reply']}", flush=True)

    time.sleep(int(result["delay"]))

    tg_response = send_business_message(
        chat_id=chat_id,
        text=result["reply"],
        business_connection_id=business_connection_id
    )

    print(f"Réponse Telegram: {tg_response}", flush=True)

    # Sauvegarde la réponse de Lily dans PostgreSQL.
    save_message(chat_id, "assistant", result["reply"])

    old_summary = user.get("summary") or ""
    new_summary = (old_summary + f"\nClient: {text}\nLily: {result['reply']}").strip()

    # Garde la mémoire courte pour éviter une DB trop lourde.
    if len(new_summary) > 1800:
        new_summary = new_summary[-1800:]

    update_user(
        chat_id=chat_id,
        stage=result["stage"],
        client_type=result["client_type"],
        interest_score=result["interest_score"],
        age_confirmed=result["age_confirmed"],
        last_message=text,
        summary=new_summary,
        username=username,
        first_name=first_name
    )

def main():
    init_db()
    print("Agent Lily Business lancé.", flush=True)
    print("En attente de messages Telegram Business...", flush=True)

    offset = None

    while True:
        try:
            data = get_updates(offset=offset, timeout=50)

            if not data.get("ok"):
                print(f"Erreur Telegram: {data}", flush=True)
                time.sleep(5)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1

                if "business_message" in update:
                    handle_business_message(update)

                elif "business_connection" in update:
                    connection = update.get("business_connection", {})
                    print("Business connection reçue:", connection, flush=True)

        except KeyboardInterrupt:
            print("Arrêt manuel.", flush=True)
            break

        except Exception as e:
            print("Erreur boucle principale:", repr(e), flush=True)
            time.sleep(5)

if __name__ == "__main__":
    main()
