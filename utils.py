import re
from html import escape
from html.parser import HTMLParser


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
    # Take the first number, so "15,000.50" is 15000 and not 1500050. The dashboard's
    # <input type="number"> also accepts exponent form ("1e5", "2.5e4"), which used to be read
    # as 1 or 2.5 and clamped up to the minimum.
    match = re.search(r"\d[\d,]*(?:\.\d+)?(?:[eE][+-]?\d+)?", str(budget_str))
    if not match:
        return default
    try:
        numeric = float(match.group().replace(",", ""))
    except (ValueError, OverflowError):
        return default
    # Clamp before int(): "1e999" is inf, and int(inf) raises OverflowError.
    return int(max(min_val, min(numeric, max_val)))


# ---------------------------------------------------------------------------
# Itinerary HTML from the model
# ---------------------------------------------------------------------------
ALLOWED_TAGS = {"div", "h1", "h2", "h3", "h4", "ul", "ol", "li", "p", "span", "strong", "b",
                "em", "i", "hr", "br", "small", "table", "thead", "tbody", "tr", "th", "td"}
VOID_TAGS = {"hr", "br"}
ALLOWED_ATTRS = {"style", "class"}
# Whole elements whose content must not reach the page at all, not even as text.
DROP_CONTENT = {"script", "style", "iframe", "object", "embed", "noscript", "template", "svg", "math"}
UNSAFE_STYLE = re.compile(r"url\s*\(|expression\s*\(|javascript:|@import|behavior\s*:", re.I)


class _ItinerarySanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.skip = 0  # depth inside a DROP_CONTENT element

    def handle_starttag(self, tag, attrs):
        if tag in DROP_CONTENT:
            self.skip += 1
            return
        if self.skip or tag not in ALLOWED_TAGS:
            return
        kept = "".join(f' {name}="{escape(value or "", quote=True)}"' for name, value in attrs
                       if name in ALLOWED_ATTRS and not (name == "style" and UNSAFE_STYLE.search(value or "")))
        self.out.append(f"<{tag}{kept}>")

    def handle_startendtag(self, tag, attrs):
        if tag in VOID_TAGS:
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in DROP_CONTENT:
            self.skip = max(0, self.skip - 1)
            return
        if not self.skip and tag in ALLOWED_TAGS and tag not in VOID_TAGS:
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(escape(data, quote=False))


def sanitize_itinerary_html(raw: str) -> str:
    """Keep only the layout HTML the itinerary prompt asks for (divs, headings, lists, text with
    inline styles). The page shows the model's reply with |safe, and the destination it plans
    for is typed by the user, so a reply carrying <script>, an onerror= handler or a
    javascript: link would otherwise run in the page and again from the trip history."""
    parser = _ItinerarySanitizer()
    parser.feed(str(raw or ""))
    parser.close()
    return "".join(parser.out)
