import os
import time
import requests

print("BOOT TEST main_lily_business.py loaded", flush=True)

from memory import (
    init_db,
    get_or_create_user,
    update_user,
    save_message,
    get_recent_messages
)

from agent import generate_lily_reply

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is missing. Add it in Railway Variables.")


def telegram_post(method, payload):
    response = requests.post(f"{API_BASE}/{method}", json=payload, timeout=30)
    try:
        return response.json()
    except Exception:
        return {"ok": False, "raw": response.text}


def get_updates(offset=None, timeout=50):
    params = {
        "timeout": timeout,
        "allowed_updates": ["message", "business_message", "business_connection"]
    }

    if offset is not None:
        params["offset"] = offset

    response = requests.get(
        f"{API_BASE}/getUpdates",
        params=params,
        timeout=timeout + 10
    )

    response.raise_for_status()
    return response.json()


def send_normal_message(chat_id, text):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True
    }
    return telegram_post("sendMessage", payload)


def send_business_message(chat_id, text, business_connection_id):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "business_connection_id": business_connection_id,
        "disable_web_page_preview": True
    }
    return telegram_post("sendMessage", payload)


def process_message(message, is_business=False):
    text = message.get("text", "")

    if not text:
        return

    # Ignore Telegram commands in normal bot chat except /start.
    # /start is useful for testing.
    if text.startswith("/") and text.strip() != "/start":
        return

    chat = message.get("chat", {})
    sender = message.get("from", {})

    chat_id = str(chat.get("id"))
    business_connection_id = message.get("business_connection_id")

    if not chat_id:
        return

    username = chat.get("username") or sender.get("username") or ""
    first_name = chat.get("first_name") or sender.get("first_name") or ""

    print("\n==============================", flush=True)
    print(f"Message reçu : {text}", flush=True)
    print(f"De : {username or first_name or chat_id}", flush=True)
    print(f"Mode : {'business' if is_business else 'normal'}", flush=True)
    print("==============================", flush=True)

    user = get_or_create_user(
        chat_id=chat_id,
        username=username,
        first_name=first_name
    )

    # If the user sends /start in normal bot mode, turn it into a natural opener.
    clean_text = "hey" if text.strip() == "/start" else text

    save_message(chat_id, "user", clean_text)

    history = get_recent_messages(chat_id, limit=20)

    print("HISTORY:", history, flush=True)

    result = generate_lily_reply(user, clean_text, history=history)

    print(f"Stage : {result['stage']}", flush=True)
    print(f"Type client : {result['client_type']}", flush=True)
    print(f"Score : {result['interest_score']}", flush=True)
    print(f"Âge confirmé : {result['age_confirmed']}", flush=True)
    print(f"Réponse dans {result['delay']} secondes", flush=True)
    reply_text = str(result.get("reply") or "").strip()

    if not reply_text:
        print("Réponse vide détectée, fallback local utilisé.", flush=True)
        reply_text = "i mean you seem interesting"
        result["reply"] = reply_text

    print(f"Réponse : {reply_text}", flush=True)

    time.sleep(int(result["delay"]))

    if is_business and business_connection_id:
        tg_response = send_business_message(
            chat_id=chat_id,
            text=reply_text,
            business_connection_id=business_connection_id
        )
    else:
        tg_response = send_normal_message(
            chat_id=chat_id,
            text=reply_text
        )

    print(f"Réponse Telegram: {tg_response}", flush=True)

    save_message(chat_id, "assistant", reply_text)

    old_summary = user.get("summary") or ""
    new_summary = (old_summary + f"\nClient: {clean_text}\nLily: {reply_text}").strip()

    if len(new_summary) > 1800:
        new_summary = new_summary[-1800:]

    update_user(
        chat_id=chat_id,
        stage=result["stage"],
        client_type=result["client_type"],
        interest_score=result["interest_score"],
        age_confirmed=result["age_confirmed"],
        last_message=clean_text,
        summary=new_summary,
        username=username,
        first_name=first_name
    )


def handle_business_message(update):
    message = update.get("business_message")
    if message:
        process_message(message, is_business=True)


def handle_normal_message(update):
    message = update.get("message")
    if message:
        process_message(message, is_business=False)


def main():
    print("BOOT TEST entering main()", flush=True)

    init_db()

    print("Agent Lily Business lancé.", flush=True)
    print("En attente de messages Telegram Business + messages normaux...", flush=True)

    offset = None

    while True:
        try:
            data = get_updates(offset=offset, timeout=50)

            if not data.get("ok"):
                print(f"Erreur Telegram: {data}", flush=True)
                time.sleep(5)
                continue

            updates = data.get("result", [])

            for update in updates:
                offset = update["update_id"] + 1

                if "business_connection" in update:
                    connection = update.get("business_connection", {})
                    print("Business connection reçue:", connection, flush=True)

                if "business_message" in update:
                    handle_business_message(update)

                elif "message" in update:
                    handle_normal_message(update)

        except KeyboardInterrupt:
            print("Arrêt manuel.", flush=True)
            break

        except Exception as e:
            print("Erreur boucle principale:", repr(e), flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
