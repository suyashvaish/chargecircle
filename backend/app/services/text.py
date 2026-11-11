import re

_TAG_RE = re.compile(r"<[^>]*>")
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_text(value: str, max_len: int = 2000) -> str:
    """Removes markup and control characters and enforces a length cap. (The UI also escapes on output.)"""
    if value is None:
        return value
    cleaned = _CTRL_RE.sub("", _TAG_RE.sub("", value)).strip()
    return cleaned[:max_len]
