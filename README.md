# Lily Business Bot v10 Stable

Replace the repository contents with these files and commit once.

Main fixes:
- direct-question routing before OpenAI
- language switching stored in PostgreSQL
- no substring false positives
- stale delayed replies cancelled
- robust Telegram Business send logging
- hard 18+ gate
- anti-409 retry
- smoke tests included

Railway variables:
TELEGRAM_BOT_TOKEN, DATABASE_URL, OPENAI_API_KEY, OPENAI_MODEL, FANVUE_LINK, DIRECT_PRODUCT_LINK, WHOP_STARTER_LINK, WHOP_PREMIUM_LINK, WHOP_VIP_LINK

Optional local smoke test:
python smoke_test.py
