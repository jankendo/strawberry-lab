"""robots.txt checks."""

from __future__ import annotations

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser


_CACHE: dict[str, RobotFileParser] = {}


def can_fetch(url: str, user_agent: str) -> bool:
    """Return true if robots.txt allows fetching URL."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = _CACHE.get(robots_url)
    if parser is None:
        parser = RobotFileParser()
        parser.set_url(robots_url)
        try:
            parser.read()
        except Exception:
            return False
        _CACHE[robots_url] = parser
    return parser.can_fetch(user_agent, url)
