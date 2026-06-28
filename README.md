# Lily Business Bot v11.1 Commercial Stable

Full replacement for the Railway/GitHub project.

## Version

`v11.1-commercial-stable`

## Offers

STARTER  
Prix: 29,99€  
Contenu: 4 images NSFW + 1 vidéo solo  
Lien: https://whop.com/lily-novalab/lily-rose-photo-pack-s  

PREMIUM  
Prix: 75€  
Contenu: 3 vidéos + 5 images  
Lien: https://whop.com/lily-novalab/premium-pack-xl-bc/  

VIP  
Désactivé. The bot must not sell VIP because it does not exist yet.

## Important fixes

- Human age gate.
- Age gate anti-spam: after repeated ignored checks, the bot stops sending the same question.
- Commercial cooldown: after a paid link, wait at least 7 client messages before pushing another offer unless the user asks price/link again.
- Starter/Premium offer selection by intent.
- Premium for "plus exclusif", videos, stronger private content.
- No invented custom requests, VIP, real meetings, direct access, fake media already sent.
- Shorter, warmer, less robotic answers.
- Fewer emojis.
- No repeated canned phrases like "you're bold".
- No unfinished endings like "ou", "or", "and".
- Keeps hard 18+ gate.

## Railway variables

Required:
- TELEGRAM_BOT_TOKEN
- DATABASE_URL
- OPENAI_API_KEY
- OPENAI_MODEL
- WHOP_STARTER_LINK
- WHOP_PREMIUM_LINK
- DIRECT_PRODUCT_LINK
- FANVUE_LINK

Optional:
- OFFER_COOLDOWN_MESSAGES, default 7

Railway logs should show:

`Agent Lily Business lancé — v11.1-commercial-stable`
