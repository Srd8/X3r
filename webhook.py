import json
import os
from http.server import BaseHTTPRequestHandler
import requests

from api._db import add_pooled_stars, record_minted_gift

BOT_TOKEN = os.environ.get("BOT_TOKEN", "5078034194:AAGCfu2i-eWZvjcQ-1P2pjlPCuaryTo8nro")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def is_en(lang_code: str) -> bool:
    return str(lang_code or "").lower().startswith("en")


class handler(BaseHTTPRequestHandler):
    def _ok(self, text="OK"):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "status": text}).encode("utf-8"))

    def do_GET(self):
        self._ok("Telegram NFT Bilingual Python Webhook Active")

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
            update = json.loads(raw)

            msg = update.get("message") or {}
            callback = update.get("callback_query") or {}
            chat_id = msg.get("chat", {}).get("id") or callback.get("message", {}).get("chat", {}).get("id")
            user_lang = (msg.get("from") or callback.get("from") or {}).get("language_code", "ar")
            host = self.headers.get("Host", "nftnjr11.vercel.app")
            base_url = f"https://{host}"

            # 1. تبديل اللغة من أزرار البوت (العربية / English)
            if callback and chat_id:
                cb_data = callback.get("data", "")
                cb_id = callback.get("id")
                requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={"callback_query_id": cb_id}, timeout=8)

                if cb_data == "lang_en":
                    requests.post(
                        f"{TELEGRAM_API}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": (
                                "🇬🇧 Welcome to **Getgems Telegram NFT Platform** 🚀🗿\n"
                                "• Select gifts, customize bundles & connect your Telegram TON Wallet inside the Mini App.\n"
                                "• Send Stars or Gifts to the bot to power free Admin NFT minting."
                            ),
                            "parse_mode": "Markdown",
                            "reply_markup": {
                                "inline_keyboard": [
                                    [{"text": "🚀 Open NFT & Wallet App (EN)", "web_app": {"url": f"{base_url}/?lang=en"}}],
                                    [{"text": "🇮🇶 التبديل إلى العربية", "callback_data": "lang_ar"}],
                                ]
                            },
                        },
                        timeout=12,
                    )
                    return self._ok()

                if cb_data == "lang_ar":
                    requests.post(
                        f"{TELEGRAM_API}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": (
                                "🇮🇶 أهلاً بك في **منصة هدايا Telegram NFT الحقيقية** 🚀🗿\n"
                                "• اختر الهدايا، خصّص الحزم، واربط محفظة تيليجرام (TON Wallet) من داخل التطبيق.\n"
                                "• أرسل نجوماً أو هدايا للبوت لدعم رصيد الإنشاء المجاني للأدمن."
                            ),
                            "parse_mode": "Markdown",
                            "reply_markup": {
                                "inline_keyboard": [
                                    [{"text": "🚀 فتح منصة الهدايا والمحفظة (AR)", "web_app": {"url": f"{base_url}/?lang=ar"}}],
                                    [{"text": "🇬🇧 Switch to English", "callback_data": "lang_en"}],
                                ]
                            },
                        },
                        timeout=12,
                    )
                    return self._ok()

            # 2. أمر /start أو /lang ثنائي اللغة
            text_cmd = (msg.get("text") or "").strip()
            if text_cmd in ("/start", "/lang") and chat_id:
                welcome_text = (
                    "🌐 **Welcome / أهلاً بك في Getgems Telegram NFT** 🚀🗿\n\n"
                    "🇬🇧 Choose gifts, upload phone artwork, and connect your Telegram Wallet in HTML Mini App; Python handles real Telegram NFT minting & Stars.\n"
                    "🇮🇶 اختر الهدايا واربط محفظة تيليجرام من واجهة التطبيق، ويتولى بايثون معالجة النجوم وإصدار هدايا NFT الحقيقية."
                )
                requests.post(
                    f"{TELEGRAM_API}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": welcome_text,
                        "parse_mode": "Markdown",
                        "reply_markup": {
                            "inline_keyboard": [
                                [
                                    {"text": "🇮🇶 فتح بالعربية", "web_app": {"url": f"{base_url}/?lang=ar"}},
                                    {"text": "🇬🇧 Open in English", "web_app": {"url": f"{base_url}/?lang=en"}},
                                ],
                                [
                                    {"text": "🇮🇶 العربية", "callback_data": "lang_ar"},
                                    {"text": "🇬🇧 English", "callback_data": "lang_en"},
                                ],
                            ]
                        },
                    },
                    timeout=12,
                )

            # 3. استقبال هدية مرسلة للبوت مباشرة
            if msg.get("gift") and chat_id:
                gift_obj = msg["gift"]
                star_val = int(gift_obj.get("star_count") or gift_obj.get("gift", {}).get("star_count") or 0)
                if star_val > 0:
                    add_pooled_stars(star_val)
                reply = (
                    f"🎁 Thank you! Received your gift ({star_val} ⭐) and added it to the bot NFT minting pool."
                    if is_en(user_lang)
                    else f"🎁 شكراً لك! تم استلام هديتك ({star_val} ⭐) وإضافتها إلى رصيد البوت لإنشاء هدايا NFT."
                )
                requests.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": reply}, timeout=12)

            # 4. الموافقة المسبقة على دفع النجوم
            if update.get("pre_checkout_query"):
                requests.post(
                    f"{TELEGRAM_API}/answerPreCheckoutQuery",
                    json={"pre_checkout_query_id": update["pre_checkout_query"]["id"], "ok": True},
                    timeout=12,
                )

            # 5. معالجة الدفع الناجح بالنجوم
            if msg.get("successful_payment") and chat_id:
                payment = msg["successful_payment"]
                payload = json.loads(payment.get("invoice_payload") or "{}")
                pay_lang = payload.get("lang") or user_lang

                if payload.get("type") == "BOT_TOPUP":
                    added = int(payment.get("total_amount") or payload.get("stars") or 0)
                    new_total = add_pooled_stars(added)
                    reply = (
                        f"⭐ Received {added} Stars in bot pool! Current balance: {new_total} ⭐."
                        if is_en(pay_lang)
                        else f"⭐ تم استلام {added} نجمة في رصيد البوت! الرصيد التشغيلي الآن: {new_total} ⭐."
                    )
                    requests.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": reply}, timeout=12)
                    return self._ok()

                gift_res = requests.post(
                    f"{TELEGRAM_API}/sendGift",
                    json={
                        "user_id": int(payload.get("recipient") or chat_id),
                        "gift_id": str(payload.get("giftId")),
                        "text": payload.get("text") or "Telegram NFT Gift 🚀",
                        "pay_for_upgrade": True,
                    },
                    timeout=15,
                ).json()

                if gift_res.get("ok"):
                    record_minted_gift(
                        {
                            "recipientId": payload.get("recipient") or chat_id,
                            "giftId": payload.get("giftId"),
                            "giftTitle": payload.get("giftTitle"),
                            "mode": "USER_STARS",
                            "starsUsed": int(payment.get("total_amount") or payload.get("starsPaid") or 0),
                            "walletAddress": payload.get("walletAddress"),
                        }
                    )

                if gift_res.get("ok"):
                    reply = (
                        "✅ Payment successful! Your real Telegram Gift has been sent and upgraded to NFT."
                        if is_en(pay_lang)
                        else "✅ تم الدفع بنجاح! تم إرسال هدية تيليجرام وترقيتها إلى NFT حقيقي في حسابك."
                    )
                else:
                    reply = (
                        f"⚠️ Stars received, but gift delivery failed: {gift_res.get('description')}"
                        if is_en(pay_lang)
                        else f"⚠️ تم استلام النجوم ولكن تعذر إرسال الهدية: {gift_res.get('description')}"
                    )
                requests.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": reply}, timeout=12)

            self._ok()
        except Exception as exc:
            print("Webhook error:", exc)
            self._ok()
