import re
import logging
import json
import threading
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum


class BlockReason(Enum):
    """Enumeration of block reasons for better categorization."""

    DOMAIN_BLOCKED = "domain_blocked"
    KEYWORD_BLOCKED = "keyword_blocked"
    PATTERN_BLOCKED = "pattern_blocked"
    WHITELIST_OVERRIDE = "whitelist_override"
    AGE_RESTRICTED = "age_restricted"
    CONTENT_TYPE = "content_type_blocked"
    CUSTOM_RULE = "custom_rule"


@dataclass
class BlockRule:
    """Data class representing a content blocking rule."""

    rule_type: str  # domain, keyword, pattern, custom
    value: str
    enabled: bool = True
    case_sensitive: bool = False
    description: str = ""
    created_date: str = ""

    def __post_init__(self):
        if not self.created_date:
            self.created_date = datetime.now().isoformat()


@dataclass
class BlockResult:
    """Result of a URL blocking check."""

    is_blocked: bool
    reason: BlockReason
    matched_rule: Optional[str] = None
    details: str = ""


class ContentBlocker:
    """
    Production-ready content blocker with advanced filtering capabilities.

    Features:
    - Domain-based blocking with subdomain support
    - Keyword filtering with context awareness
    - Pattern-based blocking (regex)
    - Whitelist override system
    - Custom blocking rules
    - Rule management and persistence
    - Audit logging
    - Performance optimization
    """

    def __init__(self, config_dir: Optional[Path] = None, app_name: str = "yt-dlp-gui"):
        self.app_name = app_name
        self.logger = logging.getLogger(f"{app_name}.blocker")
        self._lock = threading.RLock()

        # Configuration
        self.config_dir = config_dir or self._get_config_directory()
        self.rules_file = self.config_dir / "blocking_rules.json"
        self.audit_file = self.config_dir / "blocking_audit.log"

        # Rule storage
        self._domain_rules: Dict[str, BlockRule] = {}
        self._keyword_rules: Dict[str, BlockRule] = {}
        self._pattern_rules: Dict[str, Tuple[re.Pattern, BlockRule]] = {}
        self._custom_rules: Dict[str, BlockRule] = {}
        self._whitelist: Set[str] = set()

        # Performance caching
        self._block_cache: Dict[str, BlockResult] = {}
        self._cache_max_size = 1000
        self._cache_ttl = timedelta(hours=1)
        self._cache_timestamps: Dict[str, datetime] = {}

        # Statistics
        self._block_stats: Dict[str, int] = {
            "total_checks": 0,
            "blocked_requests": 0,
            "cache_hits": 0,
            "whitelist_overrides": 0,
        }

        # Initialize
        self._ensure_directories()
        self._load_default_rules()
        self._load_rules_from_file()

    def _get_config_directory(self) -> Path:
        """Get platform-specific configuration directory."""
        import platform

        system = platform.system()
        if system == "Windows":
            base = Path.home() / "AppData" / "Roaming" / self.app_name
        elif system == "Darwin":  # macOS
            base = Path.home() / "Library" / "Application Support" / self.app_name
        else:  # Linux and others
            base = Path.home() / ".config" / self.app_name

        return base

    def _ensure_directories(self) -> None:
        """Create necessary directories."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.logger.error(f"Failed to create config directory: {e}")

    def _load_default_rules(self) -> None:
        """Load default blocking rules."""
        # Default blocked domains (adult content)
        default_domains = [
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
            "chaturbate.com",
            "cam4.com",
            "livejasmin.com",
            "bongacams.com",
            "stripchat.com",
        ]

        # Default blocked keywords
        default_keywords = [
            "porn",
            "xxx",
            "sex",
            "nude",
            "naked",
            "adult",
            "nsfw",
            "erotic",
            "fetish",
            "cam",
            "strip",
            "escort",
            "prostitute",
            "sexual",
            "explicit",
            "hardcore",
            "softcore",
        ]

        # Default patterns (regex)
        default_patterns = [
            r"\b\d{2,3}x+\b",  # Patterns like "18x", "21xxx"
            r"\badult[-_]?\w*\b",  # Adult-related compound words
            r"\bxxx[-_]?\w*\b",  # XXX-related compound words
        ]

        # Add default rules if they don't exist
        for domain in default_domains:
            if domain not in self._domain_rules:
                self._domain_rules[domain] = BlockRule(
                    rule_type="domain",
                    value=domain,
                    description="Default adult content domain",
                )

        for keyword in default_keywords:
            if keyword not in self._keyword_rules:
                self._keyword_rules[keyword] = BlockRule(
                    rule_type="keyword",
                    value=keyword,
                    description="Default adult content keyword",
                )

        for pattern in default_patterns:
            if pattern not in self._pattern_rules:
                try:
                    compiled_pattern = re.compile(pattern, re.IGNORECASE)
                    rule = BlockRule(
                        rule_type="pattern",
                        value=pattern,
                        description="Default adult content pattern",
                    )
                    self._pattern_rules[pattern] = (compiled_pattern, rule)
                except re.error as e:
                    self.logger.warning(f"Invalid default pattern {pattern}: {e}")

    def is_blocked(self, url: str) -> BlockResult:
        """
        Check if a URL should be blocked.

        Args:
            url: The URL to check

        Returns:
            BlockResult with blocking decision and details
        """
        with self._lock:
            self._block_stats["total_checks"] += 1

            # Normalize URL
            url = url.strip().lower()
            if not url:
                return BlockResult(
                    False, BlockReason.DOMAIN_BLOCKED, details="Empty URL"
                )

            # Check cache first
            cached_result = self._get_cached_result(url)
            if cached_result:
                self._block_stats["cache_hits"] += 1
                return cached_result

            # Perform blocking checks
            result = self._perform_blocking_check(url)

            # Cache result
            self._cache_result(url, result)

            # Log if blocked
            if result.is_blocked:
                self._block_stats["blocked_requests"] += 1
                self._log_blocked_request(url, result)

            return result

    def _perform_blocking_check(self, url: str) -> BlockResult:
        """Perform the actual blocking check."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc or ""

            # Remove www prefix
            if domain.startswith("www."):
                domain = domain[4:]

            # Check whitelist first
            if self._is_whitelisted(domain, url):
                self._block_stats["whitelist_overrides"] += 1
                return BlockResult(
                    False, BlockReason.WHITELIST_OVERRIDE, details="URL is whitelisted"
                )

            # Domain check
            domain_result = self._check_domain_rules(domain)
            if domain_result.is_blocked:
                return domain_result

            # Keyword check
            keyword_result = self._check_keyword_rules(url)
            if keyword_result.is_blocked:
                return keyword_result

            # Pattern check
            pattern_result = self._check_pattern_rules(url)
            if pattern_result.is_blocked:
                return pattern_result

            # Custom rules check
            custom_result = self._check_custom_rules(url, parsed)
            if custom_result.is_blocked:
                return custom_result

            return BlockResult(False, BlockReason.DOMAIN_BLOCKED, details="URL allowed")

        except Exception as e:
            self.logger.error(f"Error checking URL {url}: {e}")
            # Fail safe - block on error
            return BlockResult(
                True, BlockReason.CUSTOM_RULE, details=f"Blocked due to error: {e}"
            )

    def _check_domain_rules(self, domain: str) -> BlockResult:
        """Check domain-based blocking rules."""
        for rule_domain, rule in self._domain_rules.items():
            if not rule.enabled:
                continue

            # Exact match or subdomain match
            if domain == rule_domain or domain.endswith(f".{rule_domain}"):
                return BlockResult(
                    True,
                    BlockReason.DOMAIN_BLOCKED,
                    matched_rule=rule_domain,
                    details=f"Domain blocked: {rule_domain}",
                )

        return BlockResult(False, BlockReason.DOMAIN_BLOCKED)

    def _check_keyword_rules(self, url: str) -> BlockResult:
        """Check keyword-based blocking rules."""
        for keyword, rule in self._keyword_rules.items():
            if not rule.enabled:
                continue

            search_text = url if rule.case_sensitive else url.lower()
            search_keyword = keyword if rule.case_sensitive else keyword.lower()

            # Use word boundary for more accurate matching
            pattern = rf"\b{re.escape(search_keyword)}\b"
            flags = 0 if rule.case_sensitive else re.IGNORECASE

            if re.search(pattern, search_text, flags):
                return BlockResult(
                    True,
                    BlockReason.KEYWORD_BLOCKED,
                    matched_rule=keyword,
                    details=f"Keyword blocked: {keyword}",
                )

        return BlockResult(False, BlockReason.KEYWORD_BLOCKED)

    def _check_pattern_rules(self, url: str) -> BlockResult:
        """Check regex pattern-based blocking rules."""
        for pattern_str, (compiled_pattern, rule) in self._pattern_rules.items():
            if not rule.enabled:
                continue

            if compiled_pattern.search(url):
                return BlockResult(
                    True,
                    BlockReason.PATTERN_BLOCKED,
                    matched_rule=pattern_str,
                    details=f"Pattern blocked: {pattern_str}",
                )

        return BlockResult(False, BlockReason.PATTERN_BLOCKED)

    def _check_custom_rules(self, url: str, parsed_url) -> BlockResult:
        """Check custom blocking rules."""
        # Example: Block URLs with certain query parameters
        query_params = parse_qs(parsed_url.query)

        # Block if 'adult' parameter is present
        if "adult" in query_params:
            return BlockResult(
                True,
                BlockReason.CUSTOM_RULE,
                matched_rule="adult_query_param",
                details="URL contains adult query parameter",
            )

        # Block age-restricted content indicators
        age_indicators = ["18+", "mature", "restricted", "age_gate"]
        for indicator in age_indicators:
            if indicator in url.lower():
                return BlockResult(
                    True,
                    BlockReason.AGE_RESTRICTED,
                    matched_rule=indicator,
                    details=f"Age restriction indicator: {indicator}",
                )

        return BlockResult(False, BlockReason.CUSTOM_RULE)

    def _is_whitelisted(self, domain: str, url: str) -> bool:
        """Check if domain or URL is whitelisted."""
        # Check domain whitelist
        if domain in self._whitelist:
            return True

        # Check for parent domain whitelist
        for whitelisted_domain in self._whitelist:
            if domain.endswith(f".{whitelisted_domain}"):
                return True

        return False

    def add_domain_rule(self, domain: str, description: str = "") -> bool:
        """Add a new domain blocking rule."""
        with self._lock:
            domain = domain.lower().strip()
            if domain and domain not in self._domain_rules:
                self._domain_rules[domain] = BlockRule(
                    rule_type="domain",
                    value=domain,
                    description=description or f"User-added domain: {domain}",
                )
                self._clear_cache()
                self._save_rules()
                self.logger.info(f"Added domain rule: {domain}")
                return True
            return False

    def add_keyword_rule(
        self, keyword: str, case_sensitive: bool = False, description: str = ""
    ) -> bool:
        """Add a new keyword blocking rule."""
        with self._lock:
            keyword = keyword.strip()
            if not case_sensitive:
                keyword = keyword.lower()

            if keyword and keyword not in self._keyword_rules:
                self._keyword_rules[keyword] = BlockRule(
                    rule_type="keyword",
                    value=keyword,
                    case_sensitive=case_sensitive,
                    description=description or f"User-added keyword: {keyword}",
                )
                self._clear_cache()
                self._save_rules()
                self.logger.info(f"Added keyword rule: {keyword}")
                return True
            return False

    def add_pattern_rule(self, pattern: str, description: str = "") -> bool:
        """Add a new regex pattern blocking rule."""
        with self._lock:
            try:
                compiled_pattern = re.compile(pattern, re.IGNORECASE)
                if pattern not in self._pattern_rules:
                    rule = BlockRule(
                        rule_type="pattern",
                        value=pattern,
                        description=description or f"User-added pattern: {pattern}",
                    )
                    self._pattern_rules[pattern] = (compiled_pattern, rule)
                    self._clear_cache()
                    self._save_rules()
                    self.logger.info(f"Added pattern rule: {pattern}")
                    return True
                return False
            except re.error as e:
                self.logger.error(f"Invalid regex pattern {pattern}: {e}")
                return False

    def remove_rule(self, rule_type: str, value: str) -> bool:
        """Remove a blocking rule."""
        with self._lock:
            removed = False

            if rule_type == "domain" and value in self._domain_rules:
                del self._domain_rules[value]
                removed = True
            elif rule_type == "keyword" and value in self._keyword_rules:
                del self._keyword_rules[value]
                removed = True
            elif rule_type == "pattern" and value in self._pattern_rules:
                del self._pattern_rules[value]
                removed = True

            if removed:
                self._clear_cache()
                self._save_rules()
                self.logger.info(f"Removed {rule_type} rule: {value}")
                return True
            return False

    def add_to_whitelist(self, domain: str) -> None:
        """Add a domain to the whitelist."""
        with self._lock:
            domain = domain.lower().strip()
            if domain:
                self._whitelist.add(domain)
                self._clear_cache()
                self._save_rules()
                self.logger.info(f"Added to whitelist: {domain}")

    def remove_from_whitelist(self, domain: str) -> bool:
        """Remove a domain from the whitelist."""
        with self._lock:
            domain = domain.lower().strip()
            if domain in self._whitelist:
                self._whitelist.remove(domain)
                self._clear_cache()
                self._save_rules()
                self.logger.info(f"Removed from whitelist: {domain}")
                return True
            return False

    def toggle_rule(self, rule_type: str, value: str) -> bool:
        """Toggle a rule's enabled state."""
        with self._lock:
            rule = None
            if rule_type == "domain":
                rule = self._domain_rules.get(value)
            elif rule_type == "keyword":
                rule = self._keyword_rules.get(value)
            elif rule_type == "pattern":
                rule = self._pattern_rules.get(value, (None, None))[1]

            if rule:
                rule.enabled = not rule.enabled
                self._clear_cache()
                self._save_rules()
                return True
            return False

    def get_all_rules(self) -> Dict[str, List[Dict]]:
        """Get all blocking rules."""
        with self._lock:
            return {
                "domains": [asdict(rule) for rule in self._domain_rules.values()],
                "keywords": [asdict(rule) for rule in self._keyword_rules.values()],
                "patterns": [asdict(rule) for _, rule in self._pattern_rules.values()],
                "whitelist": list(self._whitelist),
            }

    def get_statistics(self) -> Dict[str, Any]:
        """Get blocking statistics."""
        with self._lock:
            stats = self._block_stats.copy()
            stats.update(
                {
                    "total_domain_rules": len(self._domain_rules),
                    "total_keyword_rules": len(self._keyword_rules),
                    "total_pattern_rules": len(self._pattern_rules),
                    "whitelist_entries": len(self._whitelist),
                    "cache_size": len(self._block_cache),
                    "block_rate": (
                        stats["blocked_requests"] / max(1, stats["total_checks"])
                    )
                    * 100,
                }
            )
            return stats

    def clear_statistics(self) -> None:
        """Clear all statistics."""
        with self._lock:
            self._block_stats = {
                "total_checks": 0,
                "blocked_requests": 0,
                "cache_hits": 0,
                "whitelist_overrides": 0,
            }

    def _get_cached_result(self, url: str) -> Optional[BlockResult]:
        """Get cached blocking result if still valid."""
        if url not in self._block_cache:
            return None

        # Check TTL
        timestamp = self._cache_timestamps.get(url)
        if timestamp and datetime.now() - timestamp > self._cache_ttl:
            del self._block_cache[url]
            del self._cache_timestamps[url]
            return None

        return self._block_cache[url]

    def _cache_result(self, url: str, result: BlockResult) -> None:
        """Cache a blocking result."""
        # Limit cache size
        if len(self._block_cache) >= self._cache_max_size:
            # Remove oldest entries
            oldest_urls = sorted(
                self._cache_timestamps.keys(), key=lambda k: self._cache_timestamps[k]
            )[:100]

            for old_url in oldest_urls:
                self._block_cache.pop(old_url, None)
                self._cache_timestamps.pop(old_url, None)

        self._block_cache[url] = result
        self._cache_timestamps[url] = datetime.now()

    def _clear_cache(self) -> None:
        """Clear the blocking cache."""
        self._block_cache.clear()
        self._cache_timestamps.clear()

    def _log_blocked_request(self, url: str, result: BlockResult) -> None:
        """Log a blocked request for audit purposes."""
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "url": url,
                "reason": result.reason.value,
                "matched_rule": result.matched_rule,
                "details": result.details,
            }

            with open(self.audit_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")

        except OSError as e:
            self.logger.error(f"Failed to log blocked request: {e}")

    def _save_rules(self) -> None:
        """Save all rules to file."""
        try:
            rules_data = {
                "domains": {k: asdict(v) for k, v in self._domain_rules.items()},
                "keywords": {k: asdict(v) for k, v in self._keyword_rules.items()},
                "patterns": {
                    k: asdict(rule) for k, (_, rule) in self._pattern_rules.items()
                },
                "whitelist": list(self._whitelist),
                "version": "2.0",
                "last_updated": datetime.now().isoformat(),
            }

            # Atomic write with backup
            temp_file = self.rules_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(rules_data, f, indent=2, ensure_ascii=False)

            # Create backup if rules file exists
            if self.rules_file.exists():
                backup_file = self.rules_file.with_suffix(".bak")
                self.rules_file.replace(backup_file)

            temp_file.replace(self.rules_file)

        except OSError as e:
            self.logger.error(f"Failed to save blocking rules: {e}")

    def _load_rules_from_file(self) -> None:
        """Load rules from file."""
        try:
            if not self.rules_file.exists():
                return

            with open(self.rules_file, "r", encoding="utf-8") as f:
                rules_data = json.load(f)

            # Load domains
            for domain, rule_data in rules_data.get("domains", {}).items():
                self._domain_rules[domain] = BlockRule(**rule_data)

            # Load keywords
            for keyword, rule_data in rules_data.get("keywords", {}).items():
                self._keyword_rules[keyword] = BlockRule(**rule_data)

            # Load patterns
            for pattern, rule_data in rules_data.get("patterns", {}).items():
                try:
                    compiled_pattern = re.compile(pattern, re.IGNORECASE)
                    rule = BlockRule(**rule_data)
                    self._pattern_rules[pattern] = (compiled_pattern, rule)
                except re.error as e:
                    self.logger.warning(f"Skipping invalid pattern {pattern}: {e}")

            # Load whitelist
            self._whitelist = set(rules_data.get("whitelist", []))

            self.logger.info("Successfully loaded blocking rules from file")

        except (OSError, json.JSONDecodeError, TypeError) as e:
            self.logger.error(f"Failed to load blocking rules: {e}")
            # Try to load backup
            backup_file = self.rules_file.with_suffix(".bak")
            if backup_file.exists():
                try:
                    backup_file.replace(self.rules_file)
                    self._load_rules_from_file()  # Retry with backup
                except OSError:
                    pass
