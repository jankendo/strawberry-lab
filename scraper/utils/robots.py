"""robots.txt checks."""

from __future__ import annotations

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests


_CACHE: dict[str, RobotFileParser | None] = {}


def can_fetch(url: str, user_agent: str) -> bool:
    """Return True when robots rules allow this URL for the given agent."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    cached = _CACHE.get(robots_url)
    if cached is None and robots_url not in _CACHE:
        try:
            response = requests.get(
                robots_url,
                headers={"User-Agent": user_agent},
                timeout=10,
            )
        except Exception:
            return False
        if response.status_code == 404:
            _CACHE[robots_url] = None
            return True
        if not response.ok:
            return False
        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(response.text.splitlines())
        _CACHE[robots_url] = parser
        cached = parser
    if cached is None:
        return True
    return cached.can_fetch(user_agent, url)
