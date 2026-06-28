import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from agent import BOT_VERSION, generate_lily_reply
from memory import init_db, get_or_create_user, update_user, save_message, get_recent_messages

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN manquant dans Railway Variables.")

executor = ThreadPoolExecutor(max_workers=8)
_state_guard = threading.Lock()
_chat_locks = {}
_chat_versions = {}


def get_chat_lock(chat_id):
    with _state_guard:
        return _chat_locks.setdefault(chat_id, threading.Lock())


def next_version(chat_id):
    with _state_guard:
        value = _chat_versions.get(chat_id, 0) + 1
        _chat_versions[chat_id] = value
        return value


def current_version(chat_id):
    with _state_guard:
        return _chat_versions.get(chat_id, 0)


def telegram_post(method, payload):
    response = requests.post(f"{API_BASE}/{method}", json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method} error: {data}")
    return data


def get_updates(offset=None, timeout=25):
    params = {
        "timeout": timeout,
        "allowed_updates": ["message", "business_message", "business_connection"],
    }
    if offset is not None:
        params["offset"] = offset
    response = requests.get(f"{API_BASE}/getUpdates", params=params, timeout=timeout + 10)
    response.raise_for_status()
    return response.json()


def send_message(chat_id, text, business_connection_id=None):
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if business_connection_id:
        payload["business_connection_id"] = business_connection_id
    return telegram_post("sendMessage", payload)


def process_message(message, is_business=False):
    text = str(message.get("text") or "").strip()
    if not text:
        return
    if text.startswith("/") and text != "/start":
        return

    chat = message.get("chat", {})
    sender = message.get("from", {})
    chat_id = str(chat.get("id") or "")
    if not chat_id:
        return

    business_connection_id = message.get("business_connection_id")
    username = chat.get("username") or sender.get("username") or ""
    first_name = chat.get("first_name") or sender.get("first_name") or ""
    clean_text = "hey" if text == "/start" else text
    my_version = next_version(chat_id)

    print("\n==============================", flush=True)
    print(f"Message reçu : {clean_text}", flush=True)
    print(f"De : {username or first_name or chat_id}", flush=True)
    print(f"Mode : {'business' if is_business else 'normal'}", flush=True)
    print("==============================", flush=True)

    with get_chat_lock(chat_id):
        user = get_or_create_user(chat_id, username, first_name)
        save_message(chat_id, "user", clean_text)
        history = get_recent_messages(chat_id, 20)
        result = generate_lily_reply(user, clean_text, history)

    if result.get("skip_send"):
        print("Réponse ignorée volontairement : age gate déjà demandé plusieurs fois.", flush=True)
        with get_chat_lock(chat_id):
            latest_skip = get_or_create_user(chat_id, username, first_name)
            update_user(
                chat_id=chat_id,
                stage=result.get("stage", latest_skip.get("stage", "age_gate")),
                client_type=result.get("client_type", latest_skip.get("client_type", "cold")),
                interest_score=result.get("interest_score", latest_skip.get("interest_score", 0)),
                age_confirmed=result.get("age_confirmed", latest_skip.get("age_confirmed", 0)),
                last_message=clean_text,
                username=username,
                first_name=first_name,
                preferred_language=result.get("preferred_language", latest_skip.get("preferred_language", "")),
                last_intent=result.get("last_intent", latest_skip.get("last_intent", "")),
                conversation_tone=result.get("conversation_tone", latest_skip.get("conversation_tone", "neutral")),
                age_gate_count=result.get("age_gate_count", int(latest_skip.get("age_gate_count") or 0)),
            )
        return

    reply = str(result.get("reply") or "").strip() or "say that another way"
    delay = int(result.get("delay", 5))

    print(f"Stage : {result['stage']}", flush=True)
    print(f"Intent : {result.get('last_intent', '')}", flush=True)
    print(f"Langue : {result.get('preferred_language', '')}", flush=True)
    print(f"Type client : {result['client_type']}", flush=True)
    print(f"Score : {result['interest_score']}", flush=True)
    print(f"Âge confirmé : {result['age_confirmed']}", flush=True)
    print(f"Réponse dans {delay} secondes", flush=True)
    print(f"Réponse : {reply}", flush=True)

    time.sleep(delay)
    if current_version(chat_id) != my_version:
        print("Réponse annulée : message plus récent reçu.", flush=True)
        return

    try:
        tg = send_message(chat_id, reply, business_connection_id if is_business else None)
        print(f"Réponse Telegram: {tg}", flush=True)
    except Exception as exc:
        print("Erreur envoi Telegram:", repr(exc), flush=True)
        return

    with get_chat_lock(chat_id):
        save_message(chat_id, "assistant", reply)
        latest = get_or_create_user(chat_id, username, first_name)
        summary = ((latest.get("summary") or "") + f"\nClient: {clean_text}\nLily: {reply}").strip()
        if len(summary) > 2200:
            summary = summary[-2200:]
        update_user(
            chat_id=chat_id,
            stage=result["stage"],
            client_type=result["client_type"],
            interest_score=result["interest_score"],
            age_confirmed=result["age_confirmed"],
            last_message=clean_text,
            summary=summary,
            username=username,
            first_name=first_name,
            preferred_language=result.get("preferred_language", latest.get("preferred_language", "")),
            last_intent=result.get("last_intent", ""),
            conversation_tone=result.get("conversation_tone", latest.get("conversation_tone", "balanced")),
            last_offer_message_count=(
                int(latest.get("message_count") or 0) + 1
                if result.get("offer_sent")
                else int(latest.get("last_offer_message_count") or 0)
            ),
            age_gate_count=result.get("age_gate_count", int(latest.get("age_gate_count") or 0)),
        )


def main():
    init_db()
    print(f"Agent Lily Business lancé — {BOT_VERSION}", flush=True)
    print("En attente des messages Telegram...", flush=True)
    print("Pause anti-conflit Telegram : 12 secondes...", flush=True)
    time.sleep(12)

    offset = None
    while True:
        try:
            data = get_updates(offset, 25)
            if not data.get("ok"):
                print(f"Erreur Telegram: {data}", flush=True)
                time.sleep(5)
                continue
            for update in data.get("result", []):
                offset = update["update_id"] + 1
                if "business_connection" in update:
                    print("Business connection reçue:", update["business_connection"], flush=True)
                elif "business_message" in update:
                    executor.submit(process_message, update["business_message"], True)
                elif "message" in update:
                    executor.submit(process_message, update["message"], False)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            body = exc.response.text if exc.response is not None else ""
            print(f"Erreur HTTP Telegram {status}: {body}", flush=True)
            if status == 409:
                print("Conflit getUpdates : attente 65 secondes...", flush=True)
                time.sleep(65)
            else:
                time.sleep(5)
        except KeyboardInterrupt:
            break
        except Exception as exc:
            print("Erreur boucle principale:", repr(exc), flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
