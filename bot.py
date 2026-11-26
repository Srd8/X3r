import json
import os
import time
from datetime import datetime, timezone
import requests

# =========================================================
# معلومات البوت وقاعدة البيانات
# =========================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "5078034194:AAGCfu2i-eWZvjcQ-1P2pjlPCuaryTo8nro").strip()
ADMIN_ID = str(os.environ.get("ADMIN_ID", "5220076610")).strip()

# رابط قاعدة البيانات (يُقرأ من SUPABASE_URL أو DATABASE_URL أو القيمة المحددة هنا)
DATABASE_URL = (
    os.environ.get("SUPABASE_URL")
    or os.environ.get("DATABASE_URL")
    or "https://isujdshthulemghpvodm.supabase.co"
).strip().rstrip("/")

DATABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_ANON_KEY")
    or ""
).strip()

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def is_en(lang_code: str) -> bool:
    return str(lang_code or "").lower().startswith("en")


def has_db() -> bool:
    return bool(
        DATABASE_URL
        and "YOUR_PROJECT_REF" not in DATABASE_URL
        and DATABASE_KEY
        and "YOUR_SUPABASE_" not in DATABASE_KEY
    )


def _db_headers(prefer: str = "return=representation") -> dict:
    return {
        "apikey": DATABASE_KEY,
        "Authorization": f"Bearer {DATABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def db_request(path: str, method: str = "GET", payload=None):
    if not has_db():
        return None
    url = f"{DATABASE_URL}/rest/v1/{path}"
    res = requests.request(method, url, headers=_db_headers(), json=payload, timeout=15)
    if not res.ok:
        raise RuntimeError(f"DB error ({res.status_code}): {res.text}")
    return res.json() if res.text else None


def get_pooled_stars() -> int:
    if not has_db():
        return 0
    try:
        rows = db_request("bot_state?id=eq.main&select=pooled_stars")
        if isinstance(rows, list) and len(rows) > 0:
            return int(rows[0].get("pooled_stars") or 0)
        db_request("bot_state", method="POST", payload={"id": "main", "pooled_stars": 0})
        return 0
    except Exception as exc:
        print("get_pooled_stars error:", exc)
        return 0


def add_pooled_stars(delta: int) -> int:
    if not has_db():
        return 0
    try:
        current = get_pooled_stars()
        next_val = max(0, int(current) + int(delta or 0))
        db_request(
            "bot_state?id=eq.main",
            method="PATCH",
            payload={
                "pooled_stars": next_val,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return next_val
    except Exception as exc:
        print("add_pooled_stars error:", exc)
        return 0


def record_minted_gift(entry: dict):
    if not has_db():
        return None
    try:
        return db_request(
            "minted_gifts",
            method="POST",
            payload={
                "recipient_id": str(entry.get("recipientId")),
                "gift_id": str(entry.get("giftId")),
                "gift_title": entry.get("giftTitle") or f"Gift #{entry.get('giftId')}",
                "mode": entry.get("mode") or "USER_STARS",
                "stars_used": int(entry.get("starsUsed") or 0),
                "wallet_address": entry.get("walletAddress"),
                "image_url": entry.get("imageUrl"),
                "bundle_items": entry.get("bundleItems"),
                "tx_status": entry.get("txStatus") or "SENT_AND_UPGRADED_NFT",
            },
        )
    except Exception as exc:
        print("record_minted_gift error:", exc)
        return None


def tg_call(method: str, payload: dict | None = None, timeout: int = 15) -> dict:
    url = f"{TELEGRAM_API}/{method}"
    try:
        resp = requests.get(url, timeout=timeout) if payload is None else requests.post(url, json=payload, timeout=timeout)
        return resp.json()
    except Exception as exc:
        return {"ok": False, "description": str(exc)}


def send_bilingual_menu(chat_id: int | str) -> None:
    text = (
        "🌐 **Welcome / أهلاً بك في بوت هدايا Telegram NFT** 🚀🗿\n\n"
        "🇬🇧 Choose gifts & connect your Telegram Wallet in HTML; Python handles Stars, NFT gifts & database records.\n"
        "🇮🇶 اختر الهدايا واربط محفظة تيليجرام من واجهة HTML، ويتولى بايثون معالجة النجوم وإصدار هدايا NFT وقاعدة البيانات."
    )
    markup = {
        "inline_keyboard": [
            [
                {"text": "⭐ رصيد البوت / Balance", "callback_data": "bot_balance"},
                {"text": "🎁 الهدايا / Gifts", "callback_data": "list_gifts"},
            ],
            [
                {"text": "🇮🇶 العربية", "callback_data": "lang_ar"},
                {"text": "🇬🇧 English", "callback_data": "lang_en"},
            ],
        ]
    }
    tg_call("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "Markdown", "reply_markup": markup})


def handle_callback(callback: dict) -> None:
    cb_id = callback.get("id")
    cb_data = str(callback.get("data") or "")
    msg = callback.get("message") or {}
    chat_id = msg.get("chat", {}).get("id")
    user_lang = (callback.get("from") or {}).get("language_code", "ar")

    if cb_id:
        tg_call("answerCallbackQuery", {"callback_query_id": cb_id}, timeout=8)
    if not chat_id:
        return

    if cb_data == "lang_en":
        tg_call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "🇬🇧 **English Mode Active** 🚀🗿\n"
                    "• Send Stars or Gifts to this bot to power free Admin NFT minting.\n"
                    "• Use /balance or the buttons below to check bot Stars and available gifts."
                ),
                "parse_mode": "Markdown",
                "reply_markup": {
                    "inline_keyboard": [
                        [
                            {"text": "⭐ Balance", "callback_data": "bot_balance"},
                            {"text": "🎁 Gifts", "callback_data": "list_gifts"},
                        ],
                        [{"text": "🇮🇶 التبديل إلى العربية", "callback_data": "lang_ar"}],
                    ]
                },
            },
        )
    elif cb_data == "lang_ar":
        tg_call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "🇮🇶 **تم تفعيل الوضع العربي** 🚀🗿\n"
                    "• أرسل نجوماً أو هدايا للبوت لدعم رصيد الإنشاء المجاني للأدمن.\n"
                    "• استخدم /balance أو الأزرار بالأسفل لعرض الرصيد والهدايا المتاحة."
                ),
                "parse_mode": "Markdown",
                "reply_markup": {
                    "inline_keyboard": [
                        [
                            {"text": "⭐ الرصيد", "callback_data": "bot_balance"},
                            {"text": "🎁 الهدايا", "callback_data": "list_gifts"},
                        ],
                        [{"text": "🇬🇧 Switch to English", "callback_data": "lang_en"}],
                    ]
                },
            },
        )
    elif cb_data == "bot_balance":
        bal_res = tg_call("getMyStarBalance", timeout=10)
        direct_stars = int(bal_res.get("result", {}).get("star_count") or 0) if bal_res.get("ok") else 0
        total_stars = max(direct_stars, get_pooled_stars())
        reply = (
            f"⭐ **Bot Free Mint Balance:** `{total_stars}` Stars (DB: `{'Connected' if has_db() else 'Pending'}`)"
            if is_en(user_lang)
            else f"⭐ **رصيد الإنشاء المجاني للبوت:** `{total_stars}` نجمة (قاعدة البيانات: `{'متصلة' if has_db() else 'بانتظار المفتاح'}`)"
        )
        tg_call("sendMessage", {"chat_id": chat_id, "text": reply, "parse_mode": "Markdown"})
    elif cb_data == "list_gifts":
        gifts_res = tg_call("getAvailableGifts", timeout=12)
        gifts = gifts_res.get("result", {}).get("gifts", []) if gifts_res.get("ok") else []
        if not gifts:
            msg_txt = "No gifts returned from Telegram API." if is_en(user_lang) else "لم يتم إرجاع هدايا من واجهة تيليجرام حالياً."
        else:
            top = gifts[:8]
            lines = [
                f"• `#{g.get('id')}` {(g.get('sticker') or {}).get('emoji') or '🎁'} — {int(g.get('star_count') or 0) + int(g.get('upgrade_star_count') or 25)} ⭐"
                for g in top
            ]
            header = "🎁 **Available Telegram NFT Gifts (Top 8):**\n" if is_en(user_lang) else "🎁 **أبرز هدايا تيليجرام المتاحة (أول 8):**\n"
            msg_txt = header + "\n".join(lines)
        tg_call("sendMessage", {"chat_id": chat_id, "text": msg_txt, "parse_mode": "Markdown"})


def handle_message(msg: dict) -> None:
    chat_id = msg.get("chat", {}).get("id")
    if not chat_id:
        return

    user_lang = (msg.get("from") or {}).get("language_code", "ar")
    text_cmd = (msg.get("text") or "").strip()

    if text_cmd in ("/start", "/lang", "/menu"):
        send_bilingual_menu(chat_id)
        return

    if text_cmd == "/balance":
        bal_res = tg_call("getMyStarBalance", timeout=10)
        direct_stars = int(bal_res.get("result", {}).get("star_count") or 0) if bal_res.get("ok") else 0
        total_stars = max(direct_stars, get_pooled_stars())
        reply = (
            f"⭐ Balance: `{total_stars}` Stars"
            if is_en(user_lang)
            else f"⭐ الرصيد المتاح للإنشاء المجاني: `{total_stars}` نجمة"
        )
        tg_call("sendMessage", {"chat_id": chat_id, "text": reply, "parse_mode": "Markdown"})
        return

    if msg.get("gift"):
        gift_obj = msg["gift"]
        star_val = int(gift_obj.get("star_count") or gift_obj.get("gift", {}).get("star_count") or 0)
        if star_val > 0:
            add_pooled_stars(star_val)
        reply = (
            f"🎁 Received your gift ({star_val} ⭐) and added it to the bot minting pool!"
            if is_en(user_lang)
            else f"🎁 تم استلام هديتك ({star_val} ⭐) وإضافتها إلى رصيد البوت لإنشاء هدايا NFT!"
        )
        tg_call("sendMessage", {"chat_id": chat_id, "text": reply})
        return

    if msg.get("successful_payment"):
        payment = msg["successful_payment"]
        try:
            payload = json.loads(payment.get("invoice_payload") or "{}")
        except Exception:
            payload = {}
        pay_lang = payload.get("lang") or user_lang

        if payload.get("type") == "BOT_TOPUP":
            added = int(payment.get("total_amount") or payload.get("stars") or 0)
            new_total = add_pooled_stars(added)
            reply = (
                f"⭐ Received {added} Stars in bot pool! New balance: {new_total} ⭐."
                if is_en(pay_lang)
                else f"⭐ تم استلام {added} نجمة في رصيد البوت! الرصيد التشغيلي الآن: {new_total} ⭐."
            )
            tg_call("sendMessage", {"chat_id": chat_id, "text": reply})
            return

        recipient = int(payload.get("recipient") or chat_id)
        gift_id = str(payload.get("giftId") or "")
        gift_text = payload.get("text") or "Telegram NFT Gift 🚀"
        stars_paid = int(payment.get("total_amount") or payload.get("starsPaid") or 0)

        gift_res = tg_call(
            "sendGift",
            {
                "user_id": recipient,
                "gift_id": gift_id,
                "text": gift_text,
                "pay_for_upgrade": True,
            },
            timeout=15,
        )
        if gift_res.get("ok"):
            record_minted_gift(
                {
                    "recipientId": recipient,
                    "giftId": gift_id,
                    "giftTitle": payload.get("giftTitle") or f"Gift #{gift_id}",
                    "mode": "USER_STARS",
                    "starsUsed": stars_paid,
                    "walletAddress": payload.get("walletAddress"),
                }
            )
            reply = (
                "✅ Payment confirmed! Gift sent & upgraded to real NFT."
                if is_en(pay_lang)
                else "✅ تم تأكيد الدفع بنجاح! تم إرسال الهدية وترقيتها إلى NFT حقيقي."
            )
        else:
            reply = (
                f"⚠️ Stars received, but sending gift failed: {gift_res.get('description')}"
                if is_en(pay_lang)
                else f"⚠️ تم استلام النجوم ولكن تعذر إرسال الهدية: {gift_res.get('description')}"
            )
        tg_call("sendMessage", {"chat_id": chat_id, "text": reply})


def process_update(update: dict) -> None:
    if update.get("pre_checkout_query"):
        tg_call(
            "answerPreCheckoutQuery",
            {"pre_checkout_query_id": update["pre_checkout_query"]["id"], "ok": True},
            timeout=10,
        )
        return
    if update.get("callback_query"):
        handle_callback(update["callback_query"])
        return
    if update.get("message"):
        handle_message(update["message"])


def run_bot(poll_interval: float = 1.5) -> None:
    tg_call("deleteWebhook", {"drop_pending_updates": False}, timeout=10)
    offset = 0
    print(f"Bot running | Admin ID: {ADMIN_ID} | DB URL: {DATABASE_URL}")
    while True:
        res = tg_call("getUpdates", {"offset": offset, "timeout": 25}, timeout=32)
        if res.get("ok"):
            for upd in res.get("result", []):
                upd_id = int(upd.get("update_id") or 0)
                if upd_id >= offset:
                    offset = upd_id + 1
                process_update(upd)
        else:
            print("Polling warning:", res.get("description"))
            time.sleep(3)
        time.sleep(poll_interval)


if __name__ == "__main__":
    run_bot()
