# blocker.py
import re
import logging
from urllib.parse import urlparse
from typing import List

logger = logging.getLogger(__name__)


class ContentBlocker:
    """
    A simple URL-based content blocker.

    Blocks URLs if they match certain domains or contain NSFW keywords.
    Designed to be lightweight and extensible for integration with
    larger applications.
    """

    def __init__(self) -> None:
        # Predefined blocklists (normalized to lowercase)
        self._blocked_domains: List[str] = [
            "pornhub.com",
            "xvideos.com",
            "xhamster.com",
            "redtube.com",
            "youporn.com",
            "tube8.com",
            "spankbang.com",
            "xnxx.com",
            "beeg.com",
            "sex.com",
        ]

        self._blocked_keywords: List[str] = [
            "porn", "xxx", "sex", "nude", "naked",
            "adult", "nsfw", "erotic", "fetish",
            "cam", "strip", "escort",
        ]

        # Compile regex for keyword matching (word boundary helps reduce false positives)
        self._keyword_pattern = re.compile(
            r"(" + "|".join(map(re.escape, self._blocked_keywords)) + r")",
            re.IGNORECASE,
        )

    def is_blocked(self, url: str) -> bool:
        """
        Check if a URL should be blocked based on domain or keyword rules.

        Args:
            url (str): The URL to check.

        Returns:
            bool: True if blocked, False if allowed.
        """
        try:
            parsed = urlparse(url.strip().lower())
            domain = parsed.netloc or ""

            # Remove common prefixes
            if domain.startswith("www."):
                domain = domain[4:]

            # Domain check
            for blocked_domain in self._blocked_domains:
                if domain.endswith(blocked_domain):
                    logger.info(f"Blocked by domain: {domain}")
                    return True

            # Keyword check (in entire URL string)
            if self._keyword_pattern.search(url):
                logger.info(f"Blocked by keyword in URL: {url}")
                return True

            return False

        except Exception as e:
            # In production, we log and fail "safe" (better to block than allow silently).
            logger.error(f"Error parsing URL '{url}': {e}")
            return True

    # -----------------------
    # Mutators (safe methods)
    # -----------------------

    def add_blocked_domain(self, domain: str) -> None:
        """Add a new domain to the blocked list."""
        domain = domain.lower().strip()
        if domain not in self._blocked_domains:
            self._blocked_domains.append(domain)

    def remove_blocked_domain(self, domain: str) -> None:
        """Remove a domain from the blocked list."""
        domain = domain.lower().strip()
        if domain in self._blocked_domains:
            self._blocked_domains.remove(domain)

    def add_blocked_keyword(self, keyword: str) -> None:
        """Add a new keyword to the blocked list (recompiles regex)."""
        keyword = keyword.lower().strip()
        if keyword not in self._blocked_keywords:
            self._blocked_keywords.append(keyword)
            self._recompile_keywords()

    def remove_blocked_keyword(self, keyword: str) -> None:
        """Remove a keyword from the blocked list (recompiles regex)."""
        keyword = keyword.lower().strip()
        if keyword in self._blocked_keywords:
            self._blocked_keywords.remove(keyword)
            self._recompile_keywords()

    # -----------------------
    # Accessors
    # -----------------------

    def get_blocked_domains(self) -> List[str]:
        """Return a copy of blocked domains list."""
        return self._blocked_domains.copy()

    def get_blocked_keywords(self) -> List[str]:
        """Return a copy of blocked keywords list."""
        return self._blocked_keywords.copy()

    # -----------------------
    # Internal helpers
    # -----------------------

    def _recompile_keywords(self) -> None:
        """Rebuilds the regex pattern when keywords change."""
        self._keyword_pattern = re.compile(
            r"(" + "|".join(map(re.escape, self._blocked_keywords)) + r")",
            re.IGNORECASE,
        )
