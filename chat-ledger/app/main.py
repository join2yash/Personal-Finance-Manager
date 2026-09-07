from fastapi import FastAPI, Request

from app import db
from app.parser import parse_message
from app.telegram_client import send_message

app = FastAPI(title="Chat-Ledger")


@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    update = await request.json()
    message = update.get("message")
    if not message or "text" not in message:
        return {"ok": True}  # ignore non-text updates (stickers, edits, etc.)

    chat_id = message["chat"]["id"]
    text = message["text"].strip()

    user_id = db.get_or_create_user("telegram", str(chat_id))

    # ── Commands ─────────────────────────────────────────────────────────
    if text.startswith("/"):
        await handle_command(user_id, chat_id, text)
        return {"ok": True}

    # ── Regular message → parse as a Dr/Cr entry ────────────────────────
    parsed = parse_message(text)
    if parsed is None:
        await send_message(chat_id, "Couldn't find an amount in that message. Try e.g. \"500 grocery\".")
        return {"ok": True}

    cash_account_id = db.get_or_create_account(user_id, "Cash", "asset")
    category_type = "income" if parsed.direction == "income" else "expense"
    category_account_id = db.get_or_create_account(user_id, parsed.category, category_type)

    if parsed.direction == "expense":
        # Dr <Category Expense> / Cr Cash
        lines = [
            (category_account_id, parsed.amount, 0),
            (cash_account_id, 0, parsed.amount),
        ]
    else:
        # Dr Cash / Cr <Category Income>
        lines = [
            (cash_account_id, parsed.amount, 0),
            (category_account_id, 0, parsed.amount),
        ]

    db.create_journal_entry(
        user_id=user_id,
        narration=parsed.narration,
        raw_message=parsed.raw_message,
        source_platform="telegram",
        lines=lines,
    )

    new_cash_balance = db.get_balance(user_id, "Cash")
    verb = "Logged" if parsed.direction == "expense" else "Received"
    await send_message(
        chat_id,
        f"{verb} ₹{parsed.amount:.2f} under {parsed.category}.\nCash balance: ₹{new_cash_balance:.2f}",
    )
    return {"ok": True}


async def handle_command(user_id: int, chat_id: int, text: str) -> None:
    command = text.split()[0].lower()

    if command == "/balance":
        cash = db.get_balance(user_id, "Cash")
        await send_message(chat_id, f"Cash balance: ₹{cash:.2f}")

    elif command == "/undo":
        entry_id = db.get_last_entry_id(user_id)
        if entry_id is None:
            await send_message(chat_id, "Nothing to undo.")
        else:
            db.delete_entry(user_id, entry_id)
            await send_message(chat_id, "Last entry removed.")

    elif command == "/summary":
        # Phase 2 feature - stub for now so the command doesn't silently fail
        await send_message(chat_id, "Summary is coming in Phase 2 — for now try /balance.")

    else:
        await send_message(chat_id, "Unknown command. Try /balance or /undo.")
