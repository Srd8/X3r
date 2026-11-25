import json
import os
from http.server import BaseHTTPRequestHandler
import requests

from api._db import (
    has_supabase,
    get_pooled_stars,
    add_pooled_stars,
    record_minted_gift,
    get_recent_minted_gifts,
    save_custom_bundle,
    get_custom_bundles,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "5078034194:AAGCfu2i-eWZvjcQ-1P2pjlPCuaryTo8nro")
ADMIN_ID = os.environ.get("ADMIN_ID", "5220076610")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
GETGEMS_GRAPHQL = "https://api.getgems.io/graphql"


def msg_i18n(lang: str, ar_text: str, en_text: str) -> str:
    return en_text if str(lang).lower().startswith("en") else ar_text


def get_telegram_direct_stars() -> int:
    try:
        res = requests.get(f"{TELEGRAM_API}/getMyStarBalance", timeout=10).json()
        if res.get("ok") and isinstance(res.get("result", {}).get("star_count"), int):
            return res["result"]["star_count"]
    except Exception:
        pass
    return 0


def fetch_telegram_gifts() -> tuple:
    try:
        res = requests.get(f"{TELEGRAM_API}/getAvailableGifts", timeout=12).json()
        if res.get("ok") and isinstance(res.get("result", {}).get("gifts"), list):
            return res["result"]["gifts"], None
        return [], res.get("description") or "Failed to fetch gifts from Telegram Bot API"
    except Exception as exc:
        return [], str(exc)


def fetch_getgems_collections() -> list:
    query = {
        "query": """
        query {
          alphaNftCollections(first: 12) {
            edges {
              node {
                address
                name
                approximateHoldersCount
                approximateItemsCount
                floorPrice
              }
            }
          }
        }
        """
    }
    try:
        res = requests.post(GETGEMS_GRAPHQL, json=query, timeout=12).json()
        edges = res.get("data", {}).get("alphaNftCollections", {}).get("edges", [])
        return [e["node"] for e in edges if e.get("node")]
    except Exception:
        return []


class handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json(200, {"ok": True})

    def do_GET(self):
        try:
            gifts, tg_err = fetch_telegram_gifts()
            direct_stars = get_telegram_direct_stars()
            pooled_stars = get_pooled_stars()
            collections = fetch_getgems_collections()
            history = get_recent_minted_gifts(20)
            bundles = get_custom_bundles(15)

            total_free = max(int(direct_stars), int(pooled_stars))
            self._send_json(
                200,
                {
                    "ok": True,
                    "backend": "Python",
                    "dbConnected": has_supabase(),
                    "telegramGiftsError": tg_err,
                    "gifts": gifts,
                    "botDirectStars": direct_stars,
                    "pooledStars": pooled_stars,
                    "totalFreePoolStars": total_free,
                    "getgemsCollections": collections,
                    "history": history,
                    "bundles": bundles,
                },
            )
        except Exception as exc:
            self._send_json(500, {"ok": False, "error": str(exc)})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
            data = json.loads(raw)

            lang = str(data.get("lang") or "ar")
            action = data.get("action")
            user_id = str(data.get("userId") or "")
            wallet_address = str(data.get("walletAddress") or "").strip() or None

            if not user_id:
                return self._send_json(
                    400,
                    {"ok": False, "error": msg_i18n(lang, "معرف المستخدم مطلوب.", "User ID is required.")},
                )

            is_admin = user_id == str(ADMIN_ID)

            if action == "save_bundle":
                bundle_name = str(data.get("bundleName") or "").strip()
                bundle_items = data.get("bundleItems") or []
                if not bundle_name:
                    return self._send_json(
                        400,
                        {"ok": False, "error": msg_i18n(lang, "يرجى إدخال اسم الحزمة أولاً.", "Please enter a bundle name first.")},
                    )
                if not bundle_items:
                    return self._send_json(
                        400,
                        {"ok": False, "error": msg_i18n(lang, "يرجى اختيار هدية واحدة على الأقل.", "Please select at least one gift.")},
                    )
                if not has_supabase():
                    return self._send_json(
                        400,
                        {"ok": False, "error": msg_i18n(lang, "قاعدة البيانات غير متصلة في Vercel.", "Database is not connected in Vercel.")},
                    )

                total_stars = sum(int(item.get("stars") or 0) for item in bundle_items)
                saved = save_custom_bundle(
                    {
                        "creatorId": user_id,
                        "bundleName": bundle_name,
                        "items": bundle_items,
                        "totalStars": total_stars,
                    }
                )
                return self._send_json(200, {"ok": True, "bundle": saved})

            if action == "donate_to_bot":
                amount = max(1, int(data.get("donateStars") or 50))
                inv_res = requests.post(
                    f"{TELEGRAM_API}/createInvoiceLink",
                    json={
                        "title": msg_i18n(lang, "دعم رصيد البوت لإنشاء هدايا NFT", "Fund Bot Balance for NFT Gifts"),
                        "description": msg_i18n(
                            lang,
                            "إرسال نجوم تيليجرام إلى البوت لتشغيل الإنشاء المجاني للأدمن",
                            "Send Telegram Stars to fund free admin NFT gift minting",
                        ),
                        "payload": json.dumps(
                            {"type": "BOT_TOPUP", "senderId": int(user_id), "stars": amount, "lang": lang}
                        ),
                        "provider_token": "",
                        "currency": "XTR",
                        "prices": [{"label": msg_i18n(lang, "نجوم دعم البوت", "Bot Support Stars"), "amount": amount}],
                    },
                    timeout=15,
                ).json()
                if not inv_res.get("ok"):
                    return self._send_json(400, {"ok": False, "error": inv_res.get("description")})
                return self._send_json(200, {"ok": True, "mode": "INVOICE", "invoiceLink": inv_res["result"]})

            gift_id = data.get("giftId")
            if not gift_id:
                return self._send_json(
                    400,
                    {"ok": False, "error": msg_i18n(lang, "يرجى اختيار هدية تيليجرام حقيقية.", "Please select a real Telegram gift.")},
                )

            recipient = int(data.get("targetUserId") or user_id)
            gift_title = data.get("giftTitle") or f"Gift #{gift_id}"
            total_stars = int(data.get("starCount") or 0) + int(data.get("upgradeCost") or 25)
            gift_text = data.get("giftText") or msg_i18n(
                lang, "هدية Telegram NFT حقيقية 🚀🗿", "Real Telegram NFT Gift 🚀🗿"
            )
            photo_url = data.get("photoDataUrl")
            bundle_items = data.get("bundleItems") or []

            if action == "admin_free":
                if not is_admin:
                    return self._send_json(
                        403,
                        {"ok": False, "error": msg_i18n(lang, "الإنشاء المجاني مخصص للأدمن فقط.", "Free minting is restricted to Admin only.")},
                    )

                available = max(get_telegram_direct_stars(), get_pooled_stars())
                if available < total_stars:
                    return self._send_json(
                        400,
                        {
                            "ok": False,
                            "error": msg_i18n(
                                lang,
                                f"رصيد البوت ({available} ⭐) أقل من تكلفة الهدية ({total_stars} ⭐).",
                                f"Bot balance ({available} ⭐) is less than gift cost ({total_stars} ⭐).",
                            ),
                        },
                    )

                send_res = requests.post(
                    f"{TELEGRAM_API}/sendGift",
                    json={
                        "user_id": recipient,
                        "gift_id": str(gift_id),
                        "text": gift_text,
                        "pay_for_upgrade": True,
                    },
                    timeout=15,
                ).json()
                if not send_res.get("ok"):
                    return self._send_json(
                        400, {"ok": False, "error": f"Telegram API: {send_res.get('description')}"}
                    )

                if get_pooled_stars() >= total_stars:
                    add_pooled_stars(-total_stars)

                record_minted_gift(
                    {
                        "recipientId": recipient,
                        "giftId": gift_id,
                        "giftTitle": gift_title,
                        "mode": "ADMIN_FREE",
                        "starsUsed": total_stars,
                        "walletAddress": wallet_address,
                        "imageUrl": photo_url,
                        "bundleItems": bundle_items if bundle_items else None,
                    }
                )
                return self._send_json(
                    200,
                    {
                        "ok": True,
                        "mode": "ADMIN_FREE",
                        "message": msg_i18n(
                            lang,
                            f"✅ تم إرسال الهدية وترقيتها إلى NFT حقيقي للمستخدم {recipient} مجاناً ({total_stars} ⭐).",
                            f"✅ Gift sent & upgraded to real NFT for user {recipient} for FREE ({total_stars} ⭐).",
                        ),
                    },
                )

            inv_res = requests.post(
                f"{TELEGRAM_API}/createInvoiceLink",
                json={
                    "title": msg_i18n(lang, "إصدار هدية Telegram NFT حقيقية", "Mint Real Telegram NFT Gift"),
                    "description": msg_i18n(
                        lang,
                        "إرسال هدية تيليجرام وترقيتها إلى NFT حقيقي قابل للتداول على TON و Getgems",
                        "Send & upgrade a real Telegram Gift into a tradable TON / Getgems NFT",
                    ),
                    "payload": json.dumps(
                        {
                            "type": "USER_GIFT_MINT",
                            "recipient": recipient,
                            "giftId": str(gift_id),
                            "giftTitle": gift_title,
                            "text": gift_text,
                            "starsPaid": total_stars,
                            "walletAddress": wallet_address,
                            "lang": lang,
                        }
                    ),
                    "provider_token": "",
                    "currency": "XTR",
                    "prices": [
                        {
                            "label": msg_i18n(lang, "تكلفة الهدية + الترقية إلى NFT", "Gift Cost + NFT Upgrade"),
                            "amount": total_stars,
                        }
                    ],
                },
                timeout=15,
            ).json()

            if not inv_res.get("ok"):
                return self._send_json(400, {"ok": False, "error": inv_res.get("description")})

            return self._send_json(200, {"ok": True, "mode": "INVOICE", "invoiceLink": inv_res["result"]})
        except Exception as exc:
            self._send_json(500, {"ok": False, "error": str(exc)})
