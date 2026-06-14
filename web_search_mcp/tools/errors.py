"""Error message parsing, language/framework detection, and solution finding.

Parses error messages and stack traces to detect the language, framework,
error type, file location, and key terms - then searches Stack Overflow
for relevant solutions.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from .._http import get_json_client
from .._models import ErrorResponse
from .._utils import format_error

logger = logging.getLogger(__name__)

TIMEOUT = 15


@dataclass(slots=True)
class ParsedError:
    """Structured representation of a parsed error message."""

    error_type: str
    message: str
    language: str | None = None
    framework: str | None = None
    file_path: str | None = None
    line_number: int | None = None
    key_terms: list[str] = field(default_factory=list)


class ErrorParser:
    """Parses error messages and stack traces to extract key information."""

    LANGUAGE_PATTERNS: dict[str, list[str]] = {
        "rust": [
            r"error\[E\d{4}\]",
            r"cannot borrow",
            r"--> .+\.rs:\d+:\d+",
        ],
        "typescript": [
            r"at .+\.tsx?:\d+:\d+",
            r"\.tsx?:",
            r"TS\d{4}:",
        ],
        "javascript": [
            r"at .+\.jsx?:\d+:\d+",
            r"\.jsx?:",
            r"node_modules",
            r"Cannot read propert(?:y|ies)",
            r"is not defined",
        ],
        "python": [
            r'File "(.+)\.py"',
            r"Traceback \(most recent call last\)",
            r"(ImportError|AttributeError|ModuleNotFoundError)",
        ],
        "java": [
            r"at .+\.java:\d+",
            r"Exception in thread",
            r"(NullPointerException|IllegalArgumentException)",
        ],
        "go": [
            r"panic:",
            r"goroutine \d+",
            r".+\.go:\d+",
        ],
    }

    FRAMEWORK_PATTERNS: dict[str, list[str]] = {
        "react": [r"react", r"jsx", r"usestate", r"useeffect", r"usecallback"],
        "vue": [r"vue", r"@vue", r"composition-api"],
        "angular": [r"angular", r"@angular", r"ngoninit"],
        "django": [r"django", r"django\."],
        "flask": [r"flask", r"werkzeug"],
        "fastapi": [r"fastapi", r"pydantic", r"starlette"],
        "express": [r"express", r"app\.get", r"app\.post"],
        "nextjs": [r"next", r"getserversideprops", r"getstaticprops"],
    }

    ERROR_TYPE_PATTERNS: dict[str, dict[str, str]] = {
        "python": {
            "AttributeError": r"AttributeError: '(.+)' object has no attribute '(.+)'",
            "TypeError": r"TypeError: (.+)",
            "ImportError": r"(ImportError|ModuleNotFoundError): (.+)",
            "ValueError": r"ValueError: (.+)",
            "KeyError": r"KeyError: (.+)",
            "ImproperlyConfigured": r"ImproperlyConfigured: (.+)",
        },
        "javascript": {
            "CORS Error": r"CORS policy|Access-Control-Allow-Origin|No.*Access-Control",
            "Fetch Error": r"fetch.*failed|Failed to fetch|NetworkError",
            "Cannot read property": r"Cannot read propert(?:y|ies) ['\"](.+?)['\"] of",
            "undefined is not": r"undefined is not (a function|an object)",
            "null is not": r"null is not (a function|an object)",
            "TypeError": r"TypeError: (.+)",
            "ReferenceError": r"ReferenceError: (.+)",
            "SyntaxError": r"SyntaxError: (.+)",
            "RangeError": r"RangeError: (.+)",
        },
        "typescript": {
            "CORS Error": r"CORS policy|Access-Control-Allow-Origin",
            "Fetch Error": r"fetch.*failed|Failed to fetch",
            "Cannot read property": r"Cannot read propert(?:y|ies) ['\"](.+?)['\"] of",
            "TypeError": r"TypeError: (.+)",
            "ReferenceError": r"ReferenceError: (.+)",
            "SyntaxError": r"SyntaxError: (.+)",
        },
        "rust": {
            "E0382": r"error\[E0382\]",
            "E0502": r"error\[E0502\]",
            "E0308": r"error\[E0308\]",
            "borrow error": r"borrow of moved value",
            "cannot borrow": r"cannot borrow",
            "lifetime error": r"lifetime (.+) may not live long enough",
            "type mismatch": r"expected (.+), found (.+)",
        },
    }

    def parse(
        self,
        error_message: str,
        language: str | None = None,
        framework: str | None = None,
    ) -> ParsedError:
        """Parse an error message and extract key information."""
        if not language:
            language = self._detect_language(error_message)
        if not framework:
            framework = self._detect_framework(error_message)

        error_type = self._extract_error_type(error_message, language)
        file_path, line_number = self._extract_location(error_message)
        key_terms = self._extract_key_terms(error_message, error_type)
        message = self._clean_message(error_message)

        return ParsedError(
            error_type=error_type or "Unknown Error",
            message=message,
            language=language,
            framework=framework,
            file_path=file_path,
            line_number=line_number,
            key_terms=key_terms,
        )

    def _detect_language(self, text: str) -> str | None:
        """Detect programming language from error message text."""
        text_lower = text.lower()
        scores: dict[str, int] = {}
        for lang, patterns in self.LANGUAGE_PATTERNS.items():
            score = sum(1 for p in patterns if re.search(p, text_lower, re.IGNORECASE))
            if score > 0:
                scores[lang] = score
        if scores:
            return max(scores, key=lambda k: scores[k])
        return None

    def _detect_framework(self, text: str) -> str | None:
        """Detect framework from error message text."""
        text_lower = text.lower()
        for framework, patterns in self.FRAMEWORK_PATTERNS.items():
            if any(re.search(p, text_lower) for p in patterns):
                return framework
        return None

    def _extract_error_type(self, text: str, language: str | None) -> str | None:
        """Extract the error type name from the message."""
        web_errors = {
            "CORS Error": r"CORS policy|Access-Control-Allow-Origin|No.*Access-Control",
            "Fetch Error": r"fetch.*failed|Failed to fetch|NetworkError",
        }
        for error_name, pattern in web_errors.items():
            if re.search(pattern, text, re.IGNORECASE):
                return error_name

        if language and language in self.ERROR_TYPE_PATTERNS:
            for error_name, pattern in self.ERROR_TYPE_PATTERNS[language].items():
                if re.search(pattern, text, re.IGNORECASE):
                    return error_name

        match = re.search(r"([\w]+Error|[\w]+Exception):", text)
        if match:
            return match.group(1)
        return None

    def _extract_location(self, text: str) -> tuple[str | None, int | None]:
        """Extract file path and line number from stack trace."""
        match = re.search(r'File "(.+?)", line (\d+)', text)
        if match:
            return match.group(1), int(match.group(2))

        match = re.search(
            r"at (?:.+?\s+)?\(?([^\s(]+\.(?:js|ts|jsx|tsx|mjs|cjs)):(\d+):\d+\)?",
            text,
            re.IGNORECASE,
        )
        if match:
            return match.group(1), int(match.group(2))

        match = re.search(r"at ([^\s]+):(\d+):\d+", text)
        if match:
            return match.group(1), int(match.group(2))

        match = re.search(r"--> (.+?):(\d+):\d+", text)
        if match:
            return match.group(1), int(match.group(2))

        return None, None

    def _extract_key_terms(self, text: str, error_type: str | None) -> list[str]:
        """Extract key search terms from the error message."""
        terms: set[str] = set()

        if error_type:
            terms.add(error_type)

        for match in re.finditer(r"'([^']+)'|\"([^\"]+)\"", text):
            val = match.group(1) or match.group(2)
            if val and 2 < len(val) < 100:
                terms.add(val)

        for match in re.finditer(r"\b([a-z_][a-z0-9_]*\.[a-z_][a-z0-9_.]*)\b", text, re.IGNORECASE):
            terms.add(match.group(1))

        for match in re.finditer(r"\b(\d+\.\d+\.\d+)\b", text):
            terms.add(match.group(1))

        return sorted(terms)[:10]

    def _clean_message(self, text: str) -> str:
        """Clean up the error message for display."""
        text = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        if len(lines) <= 3:
            return "\n".join(lines)
        return "\n".join([*lines[:2], "...", *lines[-3:]])


# ── Stack Overflow search ──


def _search_stackoverflow(query: str, max_results: int = 5) -> list[dict]:
    """Search Stack Overflow for answers matching a query."""
    try:
        with get_json_client(timeout=TIMEOUT) as client:
            resp = client.get(
                "https://api.stackexchange.com/2.3/search/advanced",
                params={
                    "order": "desc",
                    "sort": "relevance",
                    "q": query,
                    "pagesize": min(max_results, 10),
                    "site": "stackoverflow",
                    "filter": "withbody",
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("Stack Overflow search failed: %s", e)
        return []

    results: list[dict] = []
    for item in data.get("items", []):
        body_html = item.get("body", "") or ""
        clean_excerpt = re.sub(r"<[^>]+>", "", body_html)[:500]
        results.append(
            {
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "score": item.get("score", 0),
                "answer_count": item.get("answer_count", 0),
                "accepted": item.get("accepted_answer_id") is not None,
                "excerpt": clean_excerpt,
            },
        )
    return results


# ── public API ──


def translate_error(
    error_message: str,
    max_results: int = 5,
    language: str | None = None,
) -> str | ErrorResponse:
    """Parse an error message and search Stack Overflow for solutions."""
    error_message = error_message.strip()
    if not error_message:
        return format_error("Error message must not be empty")

    parser = ErrorParser()
    parsed = parser.parse(error_message, language=language)

    if parsed.error_type == "Unknown Error" and not parsed.language:
        lines = [
            "# Error Analysis",
            "",
            "**Error type:** Unknown Error",
            "**Language:** Could not detect",
            "",
            "**Parsed message:**",
            f"```\n{parsed.message}\n```",
            "",
            "*Could not identify the error type or programming language.*",
            "",
            "Try providing a more complete error message or stack trace.",
            "",
        ]
        return "\n".join(lines)

    query_parts = []
    if parsed.error_type and parsed.error_type != "Unknown Error":
        query_parts.append(parsed.error_type)
    if parsed.key_terms:
        query_parts.extend(parsed.key_terms[:5])
    if parsed.language:
        query_parts.append(parsed.language)
    search_query = " ".join(p for p in query_parts if p)

    so_results = _search_stackoverflow(search_query, max_results=max_results)

    lines = [
        "# Error Analysis",
        "",
        f"**Error type:** {parsed.error_type}",
    ]
    if parsed.language:
        lines.append(f"**Language:** {parsed.language}")
    if parsed.framework:
        lines.append(f"**Framework:** {parsed.framework}")
    if parsed.file_path:
        loc = f"**Location:** `{parsed.file_path}`"
        if parsed.line_number:
            loc += f", line {parsed.line_number}"
        lines.append(loc)
    lines.append("")
    lines.append("**Parsed message:**")
    lines.append(f"```\n{parsed.message}\n```")
    lines.append("")

    if so_results:
        lines.append("## Stack Overflow Solutions")
        lines.append("")
        for i, r in enumerate(so_results, 1):
            badge = "✅ " if r.get("accepted") else ""
            lines.append(f"{i}. {badge}[{r['title']}]({r['link']})")
            lines.append(f"   Score: {r['score']} | Answers: {r['answer_count']}")
            excerpt = r.get("excerpt", "")
            if excerpt:
                clean = re.sub(r"<[^>]+>", "", excerpt)[:300]
                lines.append(f"   > {clean}")
            lines.append("")
    else:
        lines.append("*No Stack Overflow results found. Try broadening the error message.*")
        lines.append("")

    return "\n".join(lines)
