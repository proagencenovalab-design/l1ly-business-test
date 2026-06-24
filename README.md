# Lily Business Bot — Clean Railway Build

## Fichiers obligatoires

- `agent.py`
- `main_lily_business.py`
- `memory.py`
- `requirements.txt`
- `railway.toml`
- `.gitignore`

Les noms doivent être exacts. Ne garde pas `(1)` dans les noms de fichiers.

## Variables Railway obligatoires

Dans le service du bot :

- `TELEGRAM_BOT_TOKEN`
- `DATABASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (optionnel, valeur par défaut dans le code)
- `FANVUE_LINK`
- `DIRECT_PRODUCT_LINK`
- `WHOP_STARTER_LINK`
- `WHOP_PREMIUM_LINK`
- `WHOP_VIP_LINK`

`DATABASE_URL` doit venir du service Postgres relié au bot.

## Sécurité

- Ne mets jamais les clés dans GitHub.
- Révoque immédiatement tout token Telegram publié dans un chat ou un dépôt.
- Le hard age gate bloque toute conversation adulte avant confirmation 18+.

## Déploiement Git

```bat
git add .
git commit -m "clean railway rebuild"
git push
```

Railway redéploiera automatiquement après le push.
