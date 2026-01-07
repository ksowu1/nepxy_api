



# app/payouts/state_machine.py

class InvalidTransition(Exception):
    pass


ALLOWED = {
    "PENDING": {"SENT", "FAILED"},
    "SENT": {"CONFIRMED", "FAILED", "SENT"},  # SENT->SENT allowed for retry scheduling
    "CONFIRMED": set(),
    "FAILED": set(),
}


def assert_transition(old: str, new: str) -> None:
    if new not in ALLOWED.get(old, set()):
        raise InvalidTransition(f"Illegal payout transition: {old} -> {new}")


def assert_sent_invariant(new_status: str, provider_ref: str | None) -> None:
    """
    Invariant: if payout is SENT, it MUST have provider_ref.
    """
    if new_status == "SENT" and not provider_ref:
        raise ValueError("Invariant violation: status=SENT requires provider_ref")
