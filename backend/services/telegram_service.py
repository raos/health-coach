"""
Telegram bot service for Health Coach.

Handles incoming webhook updates, account linking via /connect <mcp_api_key>,
and a Claude tool-use loop that reuses all 14 MCP tools from mcp_server.py.
"""
import asyncio
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from config import settings
from database.engine import SessionLocal
from database.models import UserProfile

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
MAX_MSG_LEN = 4096

SYSTEM_PROMPT = """You are a personal health coach assistant accessible via Telegram.
You have tools to read and write the user's health data: workouts, nutrition, weight,
supplements, health metrics, and training/meal plans.

Keep responses concise for chat — use short sentences and bullet points rather than
long paragraphs. Emoji is fine sparingly.

When asked to log something, call the appropriate tool immediately.
When asked about data, fetch it with the right tool first, then answer.
Never make up numbers — always use tool results.

Today's date: {today}
"""


# ── Telegram HTTP helpers ─────────────────────────────────────────────────────

async def _tg(method: str, **kwargs) -> dict:
    """Call a Telegram Bot API method."""
    url = TELEGRAM_API.format(token=settings.telegram_bot_token, method=method)
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(url, json=kwargs)
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API error: {data}")
        return data.get("result", {})


async def send_message(chat_id: int, text: str) -> None:
    """Send a message, splitting at 4096-char limit if needed."""
    for chunk in _split_message(text):
        await _tg("sendMessage", chat_id=chat_id, text=chunk)


async def send_typing(chat_id: int) -> None:
    try:
        await _tg("sendChatAction", chat_id=chat_id, action="typing")
    except Exception:
        pass  # Non-critical


def _split_message(text: str, limit: int = MAX_MSG_LEN) -> list[str]:
    """Split at paragraph boundaries, falling back to hard splits."""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ""
    for paragraph in text.split("\n\n"):
        candidate = (current + "\n\n" + paragraph).lstrip("\n")
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            if len(paragraph) > limit:
                for i in range(0, len(paragraph), limit):
                    chunks.append(paragraph[i:i + limit])
                current = ""
            else:
                current = paragraph
    if current.strip():
        chunks.append(current.strip())
    return chunks or [text[:limit]]


# ── DB helpers ────────────────────────────────────────────────────────────────

def _find_by_mcp_key(db: Session, mcp_key: str) -> Optional[UserProfile]:
    from database.encryption import hmac_lookup
    return db.query(UserProfile).filter(UserProfile.mcp_api_key_lookup == hmac_lookup(mcp_key)).first()


def _find_by_chat_id(db: Session, chat_id: int) -> Optional[UserProfile]:
    return db.query(UserProfile).filter(UserProfile.telegram_chat_id == chat_id).first()


# ── Bot command handlers ──────────────────────────────────────────────────────

async def handle_start(chat_id: int, args: str) -> None:
    """/start or /start <mcp_api_key> (deep-link auto-connect)."""
    if args.strip():
        db = SessionLocal()
        try:
            profile = _find_by_mcp_key(db, args.strip())
            if profile:
                profile.telegram_chat_id = chat_id
                profile.telegram_username = None
                profile.telegram_connected_at = datetime.now(timezone.utc)
                db.commit()
                await send_message(chat_id,
                    "✅ Connected! Your Telegram is linked to your Health Coach account.\n\n"
                    "Try asking:\n"
                    "• What's my workout today?\n"
                    "• Log lunch — rice, dal, 2 eggs, ~600 kcal\n"
                    "• How did I sleep this week?\n\n"
                    "Use /help for all commands."
                )
                return
        finally:
            db.close()

    await send_message(chat_id,
        "Welcome to Health Coach!\n\n"
        "To get started, link your account:\n"
        "1. Open the Health Coach web app\n"
        "2. Go to Settings → Telegram\n"
        "3. Click Open Bot (auto-connects), or send:\n"
        "   /connect your-mcp-api-key"
    )


async def handle_connect(chat_id: int, username: Optional[str], mcp_key: str) -> None:
    """/connect <mcp_api_key>"""
    if not mcp_key.strip():
        await send_message(chat_id,
            "Usage: /connect your-mcp-api-key\n"
            "Find your key in Settings → Mobile Access."
        )
        return
    db = SessionLocal()
    try:
        profile = _find_by_mcp_key(db, mcp_key.strip())
        if not profile:
            await send_message(chat_id, "❌ Invalid key. Check Settings → Mobile Access and try again.")
            return
        profile.telegram_chat_id = chat_id
        profile.telegram_username = username
        profile.telegram_connected_at = datetime.now(timezone.utc)
        db.commit()
        await send_message(chat_id, "✅ Connected! Ask me anything about your health data.")
    finally:
        db.close()


async def handle_disconnect(chat_id: int) -> None:
    """/disconnect"""
    db = SessionLocal()
    try:
        profile = _find_by_chat_id(db, chat_id)
        if not profile:
            await send_message(chat_id, "No linked account found.")
            return
        profile.telegram_chat_id = None
        profile.telegram_username = None
        profile.telegram_connected_at = None
        db.commit()
        await send_message(chat_id, "Disconnected. Your Telegram account has been unlinked.")
    finally:
        db.close()


async def handle_help(chat_id: int) -> None:
    await send_message(chat_id,
        "Health Coach Bot\n\n"
        "Commands:\n"
        "/connect <key> — Link your account\n"
        "/disconnect — Unlink your account\n"
        "/status — Check connection status\n"
        "/help — Show this message\n\n"
        "Just chat naturally:\n"
        "• Log weight, meals, supplements\n"
        "• Ask about workouts, nutrition, health metrics\n"
        "• Get today's meal plan or workout\n"
        "• Submit your weekly check-in"
    )


async def handle_status(chat_id: int) -> None:
    db = SessionLocal()
    try:
        profile = _find_by_chat_id(db, chat_id)
        if profile:
            since = ""
            if profile.telegram_connected_at:
                since = f" since {profile.telegram_connected_at.strftime('%Y-%m-%d')}"
            await send_message(chat_id, f"✅ Connected{since}. Your health data is ready.")
        else:
            await send_message(chat_id,
                "Not connected. Use /connect &lt;your-mcp-api-key&gt; to link your account."
            )
    finally:
        db.close()


# ── Claude tool-use loop ──────────────────────────────────────────────────────

async def run_claude_tool_loop(user_id: uuid.UUID, user_message: str) -> str:
    """
    Runs a Claude tool-use conversation loop using the existing MCP tools.
    Imports list_tools() and call_tool() from mcp_server.py and sets
    _current_user_id ContextVar so all handlers are scoped to this user.
    """
    import anthropic as _anthropic
    from mcp_server import _current_user_id, list_tools, call_tool

    client = _anthropic.Anthropic(api_key=settings.anthropic_api_key)

    # Get the 14 tool definitions — same function the MCP SSE protocol uses
    mcp_tools = await list_tools()
    tools_for_api = [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.inputSchema,
        }
        for t in mcp_tools
    ]

    system = SYSTEM_PROMPT.format(today=date.today().isoformat())
    messages = [{"role": "user", "content": user_message}]

    # Set ContextVar so all MCP tool handlers scope DB queries to this user
    token = _current_user_id.set(user_id)
    try:
        for _ in range(10):  # max 10 tool-call iterations
            response = await asyncio.to_thread(
                client.messages.create,
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=system,
                tools=tools_for_api,
                messages=messages,
            )

            text_parts = []
            tool_use_blocks = []
            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_use_blocks.append(block)

            if response.stop_reason == "end_turn" or not tool_use_blocks:
                return "\n".join(text_parts) if text_parts else "Done."

            # Append Claude's turn, execute tools, append results
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in tool_use_blocks:
                try:
                    result_contents = await call_tool(block.name, block.input)
                    result_text = "\n".join(
                        c.text for c in result_contents if hasattr(c, "text")
                    )
                except Exception as exc:
                    logger.exception("Tool %s failed", block.name)
                    result_text = f"Tool error: {exc}"

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text,
                })

            messages.append({"role": "user", "content": tool_results})

        return "I reached the tool call limit. Please try a simpler request."
    finally:
        _current_user_id.reset(token)


# ── Main webhook dispatcher ───────────────────────────────────────────────────

async def handle_update(update: dict) -> None:
    """Entry point for each Telegram webhook POST."""
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat_id: int = message["chat"]["id"]
    text: str = message.get("text", "").strip()
    from_user = message.get("from", {})
    username: Optional[str] = from_user.get("username")

    if not text:
        return  # Ignore stickers, photos, etc.

    # Route bot commands
    if text.startswith("/"):
        parts = text.split(maxsplit=1)
        command = parts[0].lower().split("@")[0]  # strip @botname suffix
        args = parts[1] if len(parts) > 1 else ""

        if command == "/start":
            await handle_start(chat_id, args)
        elif command == "/connect":
            await handle_connect(chat_id, username, args)
        elif command == "/disconnect":
            await handle_disconnect(chat_id)
        elif command == "/help":
            await handle_help(chat_id)
        elif command == "/status":
            await handle_status(chat_id)
        else:
            await send_message(chat_id, "Unknown command. Use /help for a list of commands.")
        return

    # Natural language — requires linked account
    db = SessionLocal()
    try:
        profile = _find_by_chat_id(db, chat_id)
        if not profile:
            await send_message(chat_id,
                "Your Telegram isn't linked yet.\n"
                "Use /connect &lt;your-mcp-api-key&gt; to get started, "
                "or open the Health Coach app → Settings → Telegram."
            )
            return
        user_id = profile.user_id
    finally:
        db.close()

    await send_typing(chat_id)
    try:
        reply = await run_claude_tool_loop(user_id, text)
    except Exception:
        logger.exception("Claude tool loop failed for chat_id=%s", chat_id)
        reply = "Something went wrong. Please try again."

    await send_message(chat_id, reply)
