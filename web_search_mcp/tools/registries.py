"""Package registry queries for npm, PyPI, crates.io, and Go modules."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal
from urllib.parse import quote

from .._http import get_json_client
from .._utils import format_error

if TYPE_CHECKING:
    from .._models import ErrorResponse

logger = logging.getLogger(__name__)

TIMEOUT = 15

Registry = Literal["npm", "pypi", "crates", "go"]


@dataclass(slots=True)
class PackageInfo:
    """Structured metadata for a package from any registry."""

    name: str
    registry: str
    version: str
    description: str
    license: str | None = None
    downloads: str | None = None
    last_updated: str | None = None
    repository: str | None = None
    homepage: str | None = None
    dependencies_count: int | None = None
    keywords: list[str] = field(default_factory=list)


# ── helpers ──


def _fmt_downloads(n: int) -> str:
    """Human-readable download count."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _fmt_date(iso_str: str | None) -> str | None:
    """Convert ISO date string to a compact relative format."""
    if not iso_str:
        return None
    try:
        cleaned = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        delta = datetime.now(UTC) - dt
        days = delta.days
        if days < 1:
            return "today"
        if days < 30:
            return f"{days}d ago"
        if days < 365:
            return f"{days // 30}mo ago"
        return f"{days // 365}y ago"
    except (ValueError, TypeError):
        return iso_str


# ── npm ──


def _lookup_npm(name: str) -> PackageInfo | None:
    """Fetch package info from the npm public registry."""
    try:
        with get_json_client(timeout=TIMEOUT) as c:
            resp = c.get(f"https://registry.npmjs.org/{quote(name, safe='@/%')}")
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("npm lookup failed for '%s': %s", name, e)
        return None

    latest = data.get("dist-tags", {}).get("latest", "unknown")
    version_data = data.get("versions", {}).get(latest, {})
    deps = version_data.get("dependencies", {})

    downloads_str: str | None = None
    try:
        with get_json_client() as c:
            dl_resp = c.get(
                f"https://api.npmjs.org/downloads/point/last-week/{quote(name, safe='@/%')}",
            )
            if dl_resp.is_success:
                dl_data = dl_resp.json()
                dl = dl_data.get("downloads", 0)
                downloads_str = f"{_fmt_downloads(dl)}/week"
    except Exception:
        pass

    return PackageInfo(
        name=name,
        registry="npm",
        version=latest,
        description=data.get("description", ""),
        license=version_data.get("license") or data.get("license"),
        downloads=downloads_str,
        last_updated=_fmt_date(data.get("time", {}).get(latest)),
        repository=data.get("repository", {}).get("url")
        if isinstance(data.get("repository"), dict)
        else data.get("repository"),
        homepage=version_data.get("homepage") or data.get("homepage"),
        dependencies_count=len(deps),
        keywords=data.get("keywords", []),
    )


def _search_npm(query: str, max_results: int = 5) -> list[PackageInfo]:
    """Search npm by keyword."""
    try:
        with get_json_client() as c:
            resp = c.get(
                "https://registry.npmjs.org/-/v1/search",
                params={"text": query, "size": max_results},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("npm search failed for '%s': %s", query, e)
        return []

    results: list[PackageInfo] = []
    for item in data.get("objects", []):
        pkg = item.get("package", {})
        name = pkg.get("name", "")
        if not name:
            continue
        popularity = item.get("score", {}).get("detail", {}).get("popularity", 0)
        downloads = f"popularity: {popularity:.2%}" if popularity else None
        results.append(
            PackageInfo(
                name=name,
                registry="npm",
                version=pkg.get("version", "unknown"),
                description=pkg.get("description", ""),
                license=pkg.get("license"),
                downloads=downloads,
                last_updated=_fmt_date(pkg.get("date")),
                repository=pkg.get("links", {}).get("npm"),
                homepage=pkg.get("links", {}).get("homepage"),
                keywords=pkg.get("keywords", []),
            ),
        )
    return results


# ── PyPI ──


def _lookup_pypi(name: str) -> PackageInfo | None:
    """Fetch package info from PyPI JSON API."""
    try:
        with get_json_client() as c:
            resp = c.get(f"https://pypi.org/pypi/{quote(name)}/json")
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("PyPI lookup failed for '%s': %s", name, e)
        return None

    info = data.get("info", {})

    downloads_str: str | None = None
    try:
        with get_json_client() as c:
            dl_resp = c.get(f"https://pypistats.org/api/packages/{quote(name)}/recent")
            if dl_resp.is_success:
                dl_data = dl_resp.json()
                dl = dl_data.get("data", {}).get("last_week", 0)
                if dl:
                    downloads_str = f"{_fmt_downloads(dl)}/week"
    except Exception:
        pass

    return PackageInfo(
        name=name,
        registry="pypi",
        version=info.get("version", "unknown"),
        description=info.get("summary", ""),
        license=info.get("license"),
        downloads=downloads_str,
        last_updated=_fmt_date(info.get("last_modified") or info.get("upload_time")),
        repository=info.get("project_urls", {}).get("Source")
        or info.get("project_urls", {}).get("Source Code"),
        homepage=info.get("home_page") or info.get("project_urls", {}).get("Homepage"),
        dependencies_count=len(info.get("requires_dist", []) or []),
        keywords=[k.strip() for k in (info.get("keywords", "") or "").split(",") if k.strip()],
    )


def _search_pypi(query: str, max_results: int = 5) -> list[PackageInfo]:
    """Search PyPI via GitHub search (PyPI has no official search API)."""
    try:
        with get_json_client() as c:
            resp = c.get(
                "https://api.github.com/search/repositories",
                params={
                    "q": f"{query} language:python",
                    "sort": "stars",
                    "order": "desc",
                    "per_page": max_results,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("PyPI search (GitHub proxy) failed for '%s': %s", query, e)
        return []

    results: list[PackageInfo] = []
    for repo in data.get("items", []):
        name = repo.get("name", "")
        results.append(
            PackageInfo(
                name=name,
                registry="pypi",
                version="unknown",
                description=repo.get("description", ""),
                license=None,
                downloads=None,
                last_updated=_fmt_date(repo.get("updated_at")),
                repository=repo.get("html_url"),
                homepage=f"https://pypi.org/project/{name}/",
                keywords=[],
            ),
        )
    return results


# ── crates.io ──


def _lookup_crates(name: str) -> PackageInfo | None:
    """Fetch crate info from crates.io API."""
    try:
        with get_json_client() as c:
            resp = c.get(f"https://crates.io/api/v1/crates/{quote(name)}")
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("crates.io lookup failed for '%s': %s", name, e)
        return None

    crate = data.get("crate", {})
    dl = crate.get("downloads", 0)
    return PackageInfo(
        name=name,
        registry="crates.io",
        version=crate.get("max_version", "unknown"),
        description=crate.get("description", ""),
        license=crate.get("license"),
        downloads=f"{_fmt_downloads(dl)} total",
        last_updated=_fmt_date(crate.get("updated_at")),
        repository=crate.get("repository"),
        homepage=crate.get("homepage"),
        dependencies_count=None,
        keywords=crate.get("keywords", []),
    )


def _search_crates(query: str, max_results: int = 5) -> list[PackageInfo]:
    """Search crates.io by keyword."""
    try:
        with get_json_client() as c:
            resp = c.get(
                "https://crates.io/api/v1/crates",
                params={"q": query, "per_page": max_results},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("crates.io search failed for '%s': %s", query, e)
        return []

    results: list[PackageInfo] = []
    for crate in data.get("crates", []):
        name = crate.get("name", "")
        if not name:
            continue
        dl = crate.get("downloads", 0)
        results.append(
            PackageInfo(
                name=name,
                registry="crates.io",
                version=crate.get("max_version", "unknown"),
                description=crate.get("description", ""),
                license=crate.get("license"),
                downloads=f"{_fmt_downloads(dl)} total",
                last_updated=_fmt_date(crate.get("updated_at")),
                repository=crate.get("repository"),
                homepage=crate.get("homepage"),
            ),
        )
    return results


# ── Go modules ──


def _lookup_go(module: str) -> PackageInfo | None:
    """Fetch Go module info from the Go module proxy."""
    try:
        encoded = quote(module, safe="")
        with get_json_client() as c:
            resp = c.get(f"https://proxy.golang.org/{encoded}/@latest")
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("Go module lookup failed for '%s': %s", module, e)
        return None

    return PackageInfo(
        name=module,
        registry="go",
        version=data.get("Version", "unknown"),
        description=f"Go module: {module}",
        license=None,
        downloads=None,
        last_updated=_fmt_date(data.get("Time")),
        repository=f"https://{module}" if module.startswith("github.com/") else None,
        homepage=f"https://pkg.go.dev/{module}",
    )


def _search_go(query: str, max_results: int = 5) -> list[PackageInfo]:
    """Search Go modules via GitHub search for Go repos."""
    try:
        with get_json_client() as c:
            resp = c.get(
                "https://api.github.com/search/repositories",
                params={
                    "q": f"{query} language:go",
                    "sort": "stars",
                    "order": "desc",
                    "per_page": max_results,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("Go search (GitHub proxy) failed for '%s': %s", query, e)
        return []

    results: list[PackageInfo] = []
    for repo in data.get("items", []):
        full_name = repo.get("full_name", "")
        go_module = f"github.com/{full_name}"
        results.append(
            PackageInfo(
                name=go_module,
                registry="go",
                version="unknown",
                description=repo.get("description", ""),
                license=None,
                downloads=None,
                last_updated=_fmt_date(repo.get("updated_at")),
                repository=repo.get("html_url"),
                homepage=f"https://pkg.go.dev/{go_module}",
            ),
        )
    return results


# ── public API ──


def _detect_registry(name: str) -> Registry:
    """Auto-detect which registry a package name belongs to."""
    if name.startswith("@"):
        return "npm"
    if re.match(r"^github\.com/", name, re.IGNORECASE):
        return "go"
    if "." in name:
        return "pypi"
    return "npm"


def lookup_package(
    name: str,
    registry: Registry | None = None,
) -> PackageInfo | ErrorResponse:
    """Look up a specific package by name from npm, PyPI, crates.io, or Go."""
    name = name.strip()
    if not name:
        return format_error("Package name must not be empty")

    reg = registry or _detect_registry(name)

    lookup_map = {
        "npm": _lookup_npm,
        "pypi": _lookup_pypi,
        "crates": _lookup_crates,
        "go": _lookup_go,
    }

    fn = lookup_map.get(reg)
    if not fn:
        return format_error(f"Unknown registry '{reg}'", "Supported: npm, pypi, crates, go")

    result = fn(name)
    if result is None:
        return format_error(
            f"Package '{name}' not found on {reg}",
            "Check the name and registry. For PyPI use the exact package name.",
        )

    return result


def search_packages(
    query: str,
    registry: Registry = "npm",
    max_results: int = 5,
) -> list[PackageInfo] | ErrorResponse:
    """Search for packages by keyword across a registry."""
    query = query.strip()
    if not query:
        return format_error("Search query must not be empty")

    max_results = max(1, min(max_results, 20))
    search_map = {
        "npm": _search_npm,
        "pypi": _search_pypi,
        "crates": _search_crates,
        "go": _search_go,
    }

    fn = search_map.get(registry)
    if not fn:
        return format_error(f"Unknown registry '{registry}'", "Supported: npm, pypi, crates, go")

    try:
        return fn(query, max_results=max_results)
    except Exception as e:
        logger.exception("Search failed on %s", registry)
        return format_error(f"Search failed on {registry}", str(e))


# ── markdown formatters ──


def format_package_info(info: PackageInfo) -> str:
    """Render a single PackageInfo as markdown."""
    lines = [
        f"# {info.name} ({info.registry})",
        f"**Version:** {info.version}",
    ]
    if info.description:
        lines.append(f"**Description:** {info.description}")
    if info.license:
        lines.append(f"**License:** {info.license}")
    if info.downloads:
        lines.append(f"**Downloads:** {info.downloads}")
    if info.last_updated:
        lines.append(f"**Updated:** {info.last_updated}")
    if info.dependencies_count is not None:
        lines.append(f"**Dependencies:** {info.dependencies_count}")
    if info.homepage:
        lines.append(f"**Homepage:** {info.homepage}")
    if info.repository:
        lines.append(f"**Repository:** {info.repository}")
    if info.keywords:
        lines.append(f"**Keywords:** {', '.join(info.keywords[:10])}")
    return "\n".join(lines) + "\n"


def format_package_list(packages: list[PackageInfo], query: str, registry: str) -> str:
    """Render a list of packages as markdown."""
    if not packages:
        return f"No packages found for '{query}' on {registry}.\n"
    lines = [
        f"# {registry} search results for '{query}'",
        f"Found {len(packages)} packages.",
        "",
    ]
    for i, pkg in enumerate(packages, 1):
        lines.append(f"{i}. **{pkg.name}** v{pkg.version}")
        if pkg.description:
            lines.append(f"   {pkg.description[:150]}")
        parts = []
        if pkg.license:
            parts.append(pkg.license)
        if pkg.downloads:
            parts.append(f"{pkg.downloads}")
        if pkg.last_updated:
            parts.append(pkg.last_updated)
        if parts:
            lines.append(f"   {' | '.join(parts)}")
        lines.append("")
    return "\n".join(lines)
