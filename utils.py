import re


def sanitize_input(text: str, default: str = "", max_len: int = 100) -> str:
    """Sanitize user text input by stripping control characters and bounding length."""
    if not text:
        return default
    cleaned = re.sub(r"[\r\n\t]+", " ", str(text)).strip()
    return cleaned[:max_len] if cleaned else default


def validate_budget(budget_str: str, default: int = 10000, min_val: int = 1000, max_val: int = 1000000) -> int:
    """Parse and clamp budget string to realistic monetary bounds."""
    if not budget_str:
        return default
    # Take the first number, so "15,000.50" is 15000 and not 1500050.
    match = re.search(r"\d[\d,]*(?:\.\d+)?", str(budget_str))
    if not match:
        return default
    numeric = int(float(match.group().replace(",", "")))
    return max(min_val, min(numeric, max_val))
