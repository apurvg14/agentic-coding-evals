import re

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def redact(text):
    """Replace every email address in text with the literal '[redacted]'."""
    return _EMAIL.sub("[redacted]", text)
