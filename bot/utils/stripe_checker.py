import httpx
from bot.utils.logger import get_logger

logger = get_logger("stripe_checker")

STRIPE_API = "https://api.stripe.com/v1"
CHARGE_AMOUNT = 100


_STATUS_MAP = {
    "succeeded":            ("live",            "Approved \u2705"),
    "insufficient_funds":   ("insufficient",    "Insufficient Funds \u26a0\ufe0f"),
    "card_declined":        ("dead",            "Declined \u274c"),
    "incorrect_cvc":        ("ccv_error",       "Incorrect CVV \u274c"),
    "expired_card":         ("dead",            "Expired Card \u274c"),
    "processing_error":     ("error",           "Processing Error \u26a0\ufe0f"),
    "lost_card":            ("dead",            "Lost Card \U0001f6ab"),
    "stolen_card":          ("dead",            "Stolen Card \U0001f6ab"),
    "fraudulent":           ("dead",            "Fraudulent \U0001f6ab"),
    "do_not_honor":         ("dead",            "Do Not Honor \u274c"),
    "try_again_later":      ("error",           "Try Again Later \u26a0\ufe0f"),
    "not_permitted":        ("dead",            "Not Permitted \u274c"),
    "restricted_card":      ("dead",            "Restricted Card \U0001f6ab"),
    "pickup_card":          ("dead",            "Pickup Card \U0001f6ab"),
    "generic_decline":      ("dead",            "Generic Decline \u274c"),
    "currency_not_supported": ("dead",          "Currency Not Supported \u274c"),
    "testmode_decline":     ("dead",            "Test Mode Decline \u274c"),
    "approve_with_id":      ("live",            "Approved (with ID) \u2705"),
    "issuer_not_available": ("error",           "Issuer Not Available \u26a0\ufe0f"),
    "invalid_account":      ("dead",            "Invalid Account \u274c"),
    "new_account_information_available": ("error", "Account Info Changed \u26a0\ufe0f"),
    "withdrawal_count_limit_exceeded": ("insufficient", "Withdrawal Limit \u26a0\ufe0f"),
}


async def live_check(card_number: str, month: str, year: str, cvv: str,
                     stripe_key: str) -> dict:
    exp_year = int(year) + 2000 if len(year) == 2 else int(year)

    async with httpx.AsyncClient(timeout=15) as client:
        auth = (stripe_key, "")

        pm_resp = await client.post(
            f"{STRIPE_API}/payment_methods",
            auth=auth,
            data={
                "type": "card",
                "card[number]": card_number,
                "card[exp_month]": str(int(month)),
                "card[exp_year]": str(exp_year),
                "card[cvc]": cvv,
            },
        )
        pm_data = pm_resp.json()

        if pm_data.get("error"):
            err = pm_data["error"]
            decline_code = err.get("decline_code") or err.get("code") or "unknown"
            status, display = _STATUS_MAP.get(decline_code, ("dead", f"Error: {decline_code}"))
            logger.info(f"Stripe PM error: {decline_code}")
            return {
                "status": status,
                "display": display,
                "decline_code": decline_code,
                "raw_message": err.get("message", ""),
                "gate": "Stripe",
            }

        pm_id = pm_data["id"]

        pi_resp = await client.post(
            f"{STRIPE_API}/payment_intents",
            auth=auth,
            data={
                "amount": str(CHARGE_AMOUNT),
                "currency": "usd",
                "payment_method": pm_id,
                "confirm": "true",
                "automatic_payment_methods[enabled]": "false",
            },
        )
        pi_data = pi_resp.json()

        if pi_data.get("error"):
            err = pi_data["error"]
            decline_code = err.get("decline_code") or err.get("code") or "unknown"
            status, display = _STATUS_MAP.get(decline_code, ("dead", f"Declined: {decline_code}"))
            logger.info(f"Stripe PI declined: {decline_code}")

            pi_id = err.get("payment_intent", {}).get("id") if isinstance(err.get("payment_intent"), dict) else err.get("payment_intent")
            if pi_id:
                try:
                    await client.post(f"{STRIPE_API}/payment_intents/{pi_id}/cancel", auth=auth)
                except Exception:
                    pass

            return {
                "status": status,
                "display": display,
                "decline_code": decline_code,
                "raw_message": err.get("message", ""),
                "gate": "Stripe",
            }

        pi_status = pi_data.get("status", "")
        pi_id = pi_data.get("id", "")

        if pi_status == "requires_action":
            try:
                await client.post(f"{STRIPE_API}/payment_intents/{pi_id}/cancel", auth=auth)
            except Exception:
                pass
            return {
                "status": "3d_secure",
                "display": "3D Secure Required \U0001f512",
                "decline_code": "3d_secure",
                "raw_message": "Card requires 3D Secure authentication",
                "gate": "Stripe",
            }

        if pi_status == "succeeded":
            try:
                ref_resp = await client.post(
                    f"{STRIPE_API}/refunds",
                    auth=auth,
                    data={"payment_intent": pi_id},
                )
                ref_data = ref_resp.json()
                if ref_data.get("error"):
                    logger.error(f"Stripe: refund API error for {pi_id}: {ref_data['error']}")
                    return {
                        "status": "error",
                        "display": "Charged but refund failed \u26a0\ufe0f",
                        "decline_code": "refund_failed",
                        "raw_message": "Card charged $1 but auto-refund failed — check Stripe dashboard",
                        "gate": "Stripe",
                    }
                logger.info(f"Stripe: auto-refunded PI {pi_id}")
            except Exception as e:
                logger.error(f"Stripe: refund exception for {pi_id}: {e}")
                return {
                    "status": "error",
                    "display": "Charged but refund failed \u26a0\ufe0f",
                    "decline_code": "refund_failed",
                    "raw_message": "Card charged $1 but auto-refund failed — check Stripe dashboard",
                    "gate": "Stripe",
                }

            return {
                "status": "live",
                "display": "Charged & Refunded \u2705",
                "decline_code": "approved",
                "raw_message": "Card is live — charge was auto-refunded",
                "gate": "Stripe",
            }

        try:
            await client.post(f"{STRIPE_API}/payment_intents/{pi_id}/cancel", auth=auth)
        except Exception:
            pass

        return {
            "status": "unknown",
            "display": f"Unknown: {pi_status}",
            "decline_code": pi_status,
            "raw_message": "",
            "gate": "Stripe",
        }
