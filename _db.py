import os
import requests
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_ANON_KEY")
    or ""
).strip()


def has_supabase() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


def _headers(prefer: str = "return=representation") -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def sb_request(path: str, method: str = "GET", payload=None):
    if not has_supabase():
        return None
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    res = requests.request(method, url, headers=_headers(), json=payload, timeout=15)
    if not res.ok:
        raise RuntimeError(f"Supabase error ({res.status_code}): {res.text}")
    return res.json() if res.text else None


def ensure_bot_state() -> int:
    if not has_supabase():
        return 0
    rows = sb_request("bot_state?id=eq.main&select=pooled_stars")
    if isinstance(rows, list) and len(rows) > 0:
        return int(rows[0].get("pooled_stars") or 0)
    sb_request("bot_state", method="POST", payload={"id": "main", "pooled_stars": 0})
    return 0


def get_pooled_stars() -> int:
    try:
        return ensure_bot_state()
    except Exception as exc:
        print("get_pooled_stars error:", exc)
        return 0


def add_pooled_stars(delta: int) -> int:
    if not has_supabase():
        return 0
    current = ensure_bot_state()
    next_val = max(0, int(current) + int(delta or 0))
    sb_request(
        "bot_state?id=eq.main",
        method="PATCH",
        payload={
            "pooled_stars": next_val,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return next_val


def record_minted_gift(entry: dict):
    if not has_supabase():
        return None
    try:
        rows = sb_request(
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
        return rows[0] if isinstance(rows, list) and rows else rows
    except Exception as exc:
        print("record_minted_gift error:", exc)
        return None


def get_recent_minted_gifts(limit: int = 20) -> list:
    if not has_supabase():
        return []
    try:
        rows = sb_request(f"minted_gifts?select=*&order=created_at.desc&limit={limit}")
        return rows if isinstance(rows, list) else []
    except Exception as exc:
        print("get_recent_minted_gifts error:", exc)
        return []


def save_custom_bundle(bundle: dict):
    if not has_supabase():
        return None
    rows = sb_request(
        "custom_bundles",
        method="POST",
        payload={
            "creator_id": str(bundle.get("creatorId")),
            "bundle_name": str(bundle.get("bundleName")),
            "items": bundle.get("items") or [],
            "total_stars": int(bundle.get("totalStars") or 0),
        },
    )
    return rows[0] if isinstance(rows, list) and rows else rows


def get_custom_bundles(limit: int = 15) -> list:
    if not has_supabase():
        return []
    try:
        rows = sb_request(f"custom_bundles?select=*&order=created_at.desc&limit={limit}")
        return rows if isinstance(rows, list) else []
    except Exception as exc:
        print("get_custom_bundles error:", exc)
        return []
