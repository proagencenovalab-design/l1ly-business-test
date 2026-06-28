# Lily Business Bot v1.0 Stable Intelligent Sales

Full-folder stable release. Replace the entire GitHub repository root with these files.

## Version

`v1.0-stable-intelligent-sales`

## Main behavior

- Default language: English.
- French support: yes, for credibility and French-speaking prospects.
- Intelligent recovery layer: if a reply is weak, robotic, or an error happens, the bot tries to repair with AI instead of sending a canned fallback.
- Long-term memory fields:
  - sexual_profile
  - buyer_profile
  - fantasies_detected
  - objections_detected
  - trust_level
  - last_confusion
- Smart timing:
  - qualified prospects get faster replies;
  - hot buyers get short delays;
  - repair replies are quick;
  - suspected timewasters get longer delays;
  - repeated timewasters may be skipped strategically.
- Sales knowledge base included directly in `agent.py`.
- Starter/Premium offer logic included.
- VIP is not sold as a real pack because no real VIP offer exists yet.
- Strict 18+ age gate.

## Offers

Starter: 29,99€, 4 NSFW images + 1 solo video  
Premium: 75€, 3 videos + 5 images  

## Install

Upload all files to GitHub root and commit once.

Railway logs should show:

`Agent Lily Business lancé — v1.0-stable-intelligent-sales`

## Testing

Use `conversation_test_v1_0.txt` to run a full manual test conversation.

## Future interface / data tracking

This version prepares the ground for a dashboard later. The database now stores structured profile data, so a future interface can display:
- language;
- age status;
- stage;
- buyer profile;
- fantasies;
- objections;
- trust score;
- last offer;
- message counts;
- bot performance per model/account.


## Added research/data pack

This build includes an expanded internal knowledge database in `agent.py`:
- Cialdini influence principles adapted to chat.
- SPIN-style qualification adapted to short Telegram conversations.
- objection handling flow: validate, clarify, reframe, close.
- American male buyer segments.
- timewaster detection.
- BDSM/domination qualification without inventing services.
- price-sensitive and trust-skeptic handling.
- quality-check rules before sending replies.

Sources reviewed for the data pack:
- YouTube link provided: `pgjKsX4Ljnw` identified as a beginner chatting/OFM training video.
- YouTube IDs `CO2r19gAjxw` and `5PRNAkzLnz0` could not be reliably identified from public search snippets, so their content was not directly imported.
- Public sales frameworks used: SPIN selling, objection handling, Cialdini influence principles, and creator/PPV chatting discussions.


## v1.0.2 runtime stability

Fixes found during Telegram/Railway test:
- `NameError: name 'history' is not defined` inside choose_stage.
- Adds a global safety wrapper around `generate_lily_reply`, so any future internal error becomes a smooth recovery reply instead of killing the thread.
- Prevents old bot-insult history from poisoning normal future messages as timewaster.
- Never skips normal origin/language/greeting/buying questions.
- Greeting and origin replies now have shorter delays.
- Fixes punctuation like `nice,city` / `eye,what`.
- Main logs tolerate missing stage/client fields.
