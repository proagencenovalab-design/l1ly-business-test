import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor

import requests

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
    raise RuntimeError("TELEGRAM_BOT_TOKEN manquant. Ajoute-le dans Railway Variables.")

executor = ThreadPoolExecutor(max_workers=8)
_chat_locks = {}
_chat_versions = {}
_state_guard = threading.Lock()

def get_chat_lock(chat_id):
    with _state_guard:
        if chat_id not in _chat_locks:
            _chat_locks[chat_id] = threading.Lock()
        return _chat_locks[chat_id]

def next_chat_version(chat_id):
    with _state_guard:
        version = _chat_versions.get(chat_id, 0) + 1
        _chat_versions[chat_id] = version
        return version

def current_chat_version(chat_id):
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
        "allowed_updates": ["message", "business_message", "business_connection"]
    }
    if offset is not None:
        params["offset"] = offset
    response = requests.get(f"{API_BASE}/getUpdates", params=params, timeout=timeout + 10)
    response.raise_for_status()
    return response.json()

def send_normal_message(chat_id, text):
    return telegram_post("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True
    })

def send_business_message(chat_id, text, business_connection_id):
    return telegram_post("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "business_connection_id": business_connection_id,
        "disable_web_page_preview": True
    })

def process_message(message, is_business=False):
    text = str(message.get("text") or "").strip()
    if not text:
        return
    if text.startswith("/") and text != "/start":
        return

    chat = message.get("chat", {})
    sender = message.get("from", {})
    chat_id = str(chat.get("id") or "")
    business_connection_id = message.get("business_connection_id")
    if not chat_id:
        return

    my_version = next_chat_version(chat_id)
    username = chat.get("username") or sender.get("username") or ""
    first_name = chat.get("first_name") or sender.get("first_name") or ""
    clean_text = "hey" if text == "/start" else text

    print("\n==============================", flush=True)
    print(f"Message reçu : {clean_text}", flush=True)
    print(f"De : {username or first_name or chat_id}", flush=True)
    print(f"Mode : {'business' if is_business else 'normal'}", flush=True)
    print("==============================", flush=True)

    with get_chat_lock(chat_id):
        user = get_or_create_user(chat_id=chat_id, username=username, first_name=first_name)
        save_message(chat_id, "user", clean_text)
        history = get_recent_messages(chat_id, limit=20)
        result = generate_lily_reply(user, clean_text, history=history)

    reply_text = str(result.get("reply") or "").strip()
    if not reply_text:
        print("Réponse vide détectée, fallback de sécurité utilisé.", flush=True)
        reply_text = "my bad, i worded that badly"
        result["reply"] = reply_text

    print(f"Stage : {result['stage']}", flush=True)
    print(f"Type client : {result['client_type']}", flush=True)
    print(f"Score : {result['interest_score']}", flush=True)
    print(f"Âge confirmé : {result['age_confirmed']}", flush=True)
    print(f"Réponse dans {result['delay']} secondes", flush=True)
    print(f"Réponse : {reply_text}", flush=True)

    time.sleep(int(result["delay"]))

    if current_chat_version(chat_id) != my_version:
        print(f"Réponse annulée pour {chat_id}: un message plus récent est arrivé.", flush=True)
        return

    if is_business and business_connection_id:
        tg_response = send_business_message(chat_id, reply_text, business_connection_id)
    else:
        tg_response = send_normal_message(chat_id, reply_text)

    print(f"Réponse Telegram: {tg_response}", flush=True)

    with get_chat_lock(chat_id):
        save_message(chat_id, "assistant", reply_text)
        latest_user = get_or_create_user(chat_id=chat_id, username=username, first_name=first_name)
        old_summary = latest_user.get("summary") or ""
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

def main():
    init_db()
    print("Agent Lily Business lancé.", flush=True)
    print("En attente des messages Telegram...", flush=True)
    print("Pause anti-conflit Telegram : 12 secondes...", flush=True)
    time.sleep(12)

    offset = None
    while True:
        try:
            data = get_updates(offset=offset, timeout=25)
            if not data.get("ok"):
                print(f"Erreur Telegram: {data}", flush=True)
                time.sleep(5)
                continue
            for update in data.get("result", []):
                offset = update["update_id"] + 1
                if "business_connection" in update:
                    print("Business connection reçue:", update.get("business_connection", {}), flush=True)
                elif "business_message" in update:
                    executor.submit(process_message, update["business_message"], True)
                elif "message" in update:
                    executor.submit(process_message, update["message"], False)
        except KeyboardInterrupt:
            print("Arrêt manuel.", flush=True)
            break
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            body = exc.response.text if exc.response is not None else ""
            print(f"Erreur HTTP Telegram {status}: {body}", flush=True)
            if status == 409:
                print("Conflit getUpdates détecté. Attente de 65 secondes avant nouvel essai...", flush=True)
                time.sleep(65)
            else:
                time.sleep(5)
        except Exception as exc:
            print("Erreur boucle principale:", repr(exc), flush=True)
            time.sleep(5)

if __name__ == "__main__":
    main()
