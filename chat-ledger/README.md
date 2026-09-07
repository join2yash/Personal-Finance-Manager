# Chat-Ledger — Phase 0/1 Starter

Telegram bot that parses chat messages into balanced Dr/Cr journal entries.
Matches Phase 0–1 of the build plan: multi-tenant partitioned schema, regex
parser, `/balance` and `/undo` commands.

To try : https://t.me/AI_AllExp_bot

## What's here

```
schema.sql             Partitioned Postgres schema (users, accounts, journal_entries, entry_lines)
app/parser.py           Amount + keyword extraction (no external AI dependency)
app/db.py               All DB access — every function requires a user_id
app/telegram_client.py  Thin wrapper for the Telegram Bot API
app/main.py             FastAPI app + webhook endpoint
tests/test_parser.py    Unit tests for the parser (no DB/network needed)
```

## 1. Create your Telegram bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. `/newbot`, follow the prompts
3. Copy the token it gives you

## 2. Set up Postgres

Any Postgres 13+ works (hash partitioning needs PG11+, but use 13+ for `DO` block support used here).

- Local: `createdb chatledger`
- Hosted: Supabase, Railway, or Render all have free tiers — copy the connection string

Run the schema:
```bash
psql "$DATABASE_URL" -f schema.sql
```

## 3. Configure environment

```bash
cp .env.example .env
# edit .env: paste your BOT_TOKEN and DATABASE_URL
```

## 4. Install & run locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python3 tests/test_parser.py   # sanity check, no network/DB needed

export $(cat .env | xargs)     # loads BOT_TOKEN and DATABASE_URL
uvicorn app.main:app --reload --port 8000
```

## 5. Expose it to Telegram

Telegram needs a public HTTPS URL to send webhook updates to.

**Local testing:** use [ngrok](https://ngrok.com/):
```bash
ngrok http 8000
```
Copy the `https://...ngrok-free.app` URL it gives you.

**Register the webhook:**
```bash
curl -X POST "https://api.telegram.org/bot$BOT_TOKEN/setWebhook" \
  -d "url=https://YOUR_PUBLIC_URL/webhook/telegram"
```

Now message your bot on Telegram — try `500 grocery` or `received 2000 salary`.

## 6. Deploy for real

Once it works locally, deploy `app/` to Railway or Render (both support FastAPI
out of the box), point `DATABASE_URL` at your hosted Postgres, and re-run the
`setWebhook` call with your deployed URL instead of the ngrok one.

## Known simplifications (fine for MVP, revisit before scaling)

- No auth/rate-limiting on the webhook endpoint — add a Telegram secret token
  check before going public
- `entry_lines.account_id`/`entry_id` referential integrity is enforced in
  `app/db.py`, not as a DB foreign key (Postgres partitioning constraint — see
  comment in `schema.sql`)
- `/summary` is a stub — Phase 2 feature per the build plan
- WhatsApp + identity-linking (build plan §7) isn't implemented yet — this is
  Telegram-only, Phase 0–1 scope
