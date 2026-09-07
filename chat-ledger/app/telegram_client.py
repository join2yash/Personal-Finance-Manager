import os
import httpx

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


async def send_message(chat_id: int, text: str) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(f"{API_BASE}/sendMessage", json={"chat_id": chat_id, "text": text})


async def set_webhook(public_url: str) -> dict:
    """Call once after deployment to point Telegram at your webhook endpoint."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{API_BASE}/setWebhook", json={"url": public_url})
        return resp.json()
