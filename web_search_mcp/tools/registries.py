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
