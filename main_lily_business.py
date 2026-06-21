import os
import time
import json
import requests

from memory import init_db, get_or_create_user, update_user
from agent import generate_lily_reply


BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN manquant. Utilise set TELEGRAM_BOT_TOKEN=TON_TOKEN")

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_business_message(chat_id, business_connection_id, text):
    payload = {
        "chat_id": chat_id,
        "business_connection_id": business_connection_id,
        "text": text
    }

    response = requests.post(
        f"{BASE_URL}/sendMessage",
        json=payload,
        timeout=20
    )

    data = response.json()
    print("Réponse Telegram:", data)

    return data


def main():
    init_db()

    offset = None

    print("Agent Lily Business lancé.")
    print("En attente de messages Telegram Business...")

    while True:
        params = {
            "timeout": 30,
            "allowed_updates": json.dumps([
                "business_message",
                "business_connection"
            ])
        }

        if offset:
            params["offset"] = offset

        try:
            response = requests.get(
                f"{BASE_URL}/getUpdates",
                params=params,
                timeout=35
            )

            data = response.json()

            if not data.get("ok"):
                print("Erreur Telegram:", data)
                time.sleep(5)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1

                if "business_message" not in update:
                    continue

                msg = update["business_message"]

                if "text" not in msg:
                    print("Message ignoré : pas de texte.")
                    continue

                business_connection_id = msg["business_connection_id"]
                chat_id = msg["chat"]["id"]
                username = msg["chat"].get("username", "")
                first_name = msg["chat"].get("first_name", "")
                text = msg.get("text", "")

                print("\n==============================")
                print("Message reçu :", text)
                print("De :", username or first_name or chat_id)
                print("==============================")

                user = get_or_create_user(
                    chat_id=chat_id,
                    username=username,
                    first_name=first_name
                )

                result = generate_lily_reply(user, text)

                reply = result["reply"]
                delay = result["delay"]

                old_summary = user["summary"] or ""
                new_summary = old_summary + f"\nClient: {text}\nLily: {reply}"
                new_summary = new_summary[-2000:]

                update_user(
                    chat_id,
                    username=username,
                    first_name=first_name,
                    stage=result["stage"],
                    client_type=result["client_type"],
                    interest_score=result["interest_score"],
                    age_confirmed=result["age_confirmed"],
                    message_count=int(user["message_count"]) + 1,
                    last_message=text,
                    summary=new_summary
                )

                print("Stage :", result["stage"])
                print("Type client :", result["client_type"])
                print("Score :", result["interest_score"])
                print("Âge confirmé :", result["age_confirmed"])
                print("Réponse dans", delay, "secondes")
                print("Réponse :", reply)

                time.sleep(delay)

                send_business_message(
                    chat_id=chat_id,
                    business_connection_id=business_connection_id,
                    text=reply
                )

        except KeyboardInterrupt:
            print("\nArrêt manuel.")
            break

        except Exception as e:
            print("Erreur générale:", e)
            time.sleep(5)


if __name__ == "__main__":
    main()