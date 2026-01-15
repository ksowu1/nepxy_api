import logging

from services.redaction import redact_dict, redact_text


def test_redact_text_masks_phone_email_and_tokens():
    text = "User ksowu190@gmail.com phone +22890009911 token Bearer abcdef"
    redacted = redact_text(text)
    assert "ksowu190@gmail.com" not in redacted
    assert "+22890009911" not in redacted
    assert redacted == "[REDACTED]"


def test_redact_dict_masks_sensitive_keys():
    payload = {
        "email": "ksowu190@gmail.com",
        "phone_e164": "+22890009911",
        "access_token": "abc",
        "refresh_token": "def",
        "X-Signature": "sha256=deadbeef",
    }
    redacted = redact_dict(payload)
    assert redacted["email"] == "k***@gmail.com"
    assert redacted["phone_e164"] == "+22890****11"
    assert redacted["access_token"] == "[REDACTED]"
    assert redacted["refresh_token"] == "[REDACTED]"
    assert redacted["X-Signature"] == "[REDACTED]"


def test_log_line_uses_redaction_helper(caplog):
    logger = logging.getLogger("redaction-test")
    caplog.set_level(logging.INFO)
    msg = redact_text("email ksowu190@gmail.com phone +22890009911 token Bearer abcdef")
    logger.info("payload=%s", msg)
    assert "ksowu190@gmail.com" not in caplog.text
    assert "+22890009911" not in caplog.text
