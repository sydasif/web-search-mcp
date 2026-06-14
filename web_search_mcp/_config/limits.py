"""Business logic constants: depth limits, enrichment limits, timeouts."""

DEPTH_LIMITS: dict[str, dict[str, int]] = {
    "github": {"quick": 15, "default": 30, "deep": 60},
    "hackernews": {"quick": 15, "default": 30, "deep": 60},
    "reddit": {"quick": 10, "default": 25, "deep": 50},
    "x": {"quick": 12, "default": 30, "deep": 60},
}

ENRICH_LIMITS: dict[str, dict[str, int]] = {
    "github": {"quick": 3, "default": 5, "deep": 8},
    "hackernews": {"quick": 3, "default": 5, "deep": 10},
    "reddit": {"quick": 3, "default": 5, "deep": 8},
}

FEED_TIMEOUT = 15
