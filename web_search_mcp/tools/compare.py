"""Technology comparison tool.

Fetches GitHub stats, npm/PyPI registry data, and license information
to produce side-by-side comparisons of two technologies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from .._http import get_json_client
from .registries import PackageInfo, lookup_package

logger = logging.getLogger(__name__)

TIMEOUT = 15

Category = Literal["framework", "library", "database", "language", "tool"]


@dataclass(slots=True)
class TechInfo:
    """Normalised information about a technology from multiple sources."""

    name: str
    category: str = "library"
    github_stars: int | None = None
    github_language: str | None = None
    github_open_issues: int | None = None
    github_description: str | None = None
    registry_version: str | None = None
    registry_downloads: str | None = None
    registry_license: str | None = None
    last_updated: str | None = None
    homepage: str | None = None


_GITHUB_REPOS: dict[str, str] = {
    "react": "facebook/react",
    "vue": "vuejs/core",
    "angular": "angular/angular",
    "next.js": "vercel/next.js",
    "nuxt": "nuxt/nuxt",
    "svelte": "sveltejs/svelte",
    "django": "django/django",
    "flask": "pallets/flask",
    "fastapi": "fastapi/fastapi",
    "express": "expressjs/express",
    "spring": "spring-projects/spring-framework",
    "rails": "rails/rails",
    "laravel": "laravel/laravel",
    "symfony": "symfony/symfony",
    "nextjs": "vercel/next.js",
    "pandas": "pandas-dev/pandas",
    "numpy": "numpy/numpy",
    "requests": "psf/requests",
    "httpx": "encode/httpx",
    "pytest": "pytest-dev/pytest",
    "ruff": "astral-sh/ruff",
    "uv": "astral-sh/uv",
    "lodash": "lodash/lodash",
    "axios": "axios/axios",
    "jquery": "jquery/jquery",
    "three.js": "mrdoob/three.js",
    "d3.js": "d3/d3",
    "postgresql": "postgres/postgres",
    "mysql": "mysql/mysql-server",
    "mongodb": "mongodb/mongo",
    "redis": "redis/redis",
    "sqlite": "sqlite/sqlite",
    "clickhouse": "clickhouse/clickhouse",
    "python": "python/cpython",
    "rust": "rust-lang/rust",
    "go": "golang/go",
    "typescript": "microsoft/TypeScript",
    "javascript": "tc39/ecma262",
    "docker": "moby/moby",
    "kubernetes": "kubernetes/kubernetes",
    "ansible": "ansible/ansible",
    "terraform": "hashicorp/terraform",
    "webpack": "webpack/webpack",
    "vite": "vitejs/vite",
    "esbuild": "evanw/esbuild",
    "uvicorn": "encode/uvicorn",
    "celery": "celery/celery",
    "redis-py": "redis/redis-py",
    "postgres": "postgres/postgres",
    "three": "mrdoob/three.js",
    "d3": "d3/d3",
    "pytorch": "pytorch/pytorch",
    "tensorflow": "tensorflow/tensorflow",
    "jax": "google/jax",
}

_NPM_NAMES: dict[str, str] = {
    "react": "react",
    "vue": "vue",
    "angular": "@angular/core",
    "next.js": "next",
    "nextjs": "next",
    "nuxt": "nuxt",
    "svelte": "svelte",
    "express": "express",
    "lodash": "lodash",
    "axios": "axios",
    "jquery": "jquery",
    "three.js": "three",
    "three": "three",
    "d3.js": "d3",
    "d3": "d3",
    "webpack": "webpack",
    "vite": "vite",
    "esbuild": "esbuild",
    "uvicorn": "uvicorn",
    "celery": "celery",
    "pytest": "pytest",
    "ruff": "ruff",
    "httpx": "httpx",
}

_PYPI_NAMES: dict[str, str] = {
    "django": "Django",
    "flask": "Flask",
    "fastapi": "fastapi",
    "pandas": "pandas",
    "numpy": "numpy",
    "requests": "requests",
    "httpx": "httpx",
    "pytest": "pytest",
    "ruff": "ruff",
    "celery": "celery",
    "uvicorn": "uvicorn",
    "pytorch": "torch",
    "tensorflow": "tensorflow",
    "jax": "jax",
    "ansible": "ansible",
    "boto3": "boto3",
}


def _fetch_github(repo: str) -> dict | None:
    """Fetch repository metadata from the GitHub API."""
    try:
        with get_json_client(timeout=TIMEOUT) as c:
            resp = c.get(f"https://api.github.com/repos/{repo}")
            if resp.status_code == 403:
                logger.warning("GitHub API rate limited for %s", repo)
                return None
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.debug("GitHub fetch failed for %s: %s", repo, e)
        return None

    lic = data.get("license")
    return {
        "stars": data.get("stargazers_count"),
        "language": data.get("language"),
        "open_issues": data.get("open_issues_count"),
        "description": data.get("description"),
        "updated_at": data.get("updated_at"),
        "license": lic.get("spdx_id") if isinstance(lic, dict) else None,
        "homepage": data.get("homepage") or data.get("html_url"),
    }


def gather_info(name: str, category: str = "library") -> TechInfo:
    """Gather information about a technology from multiple sources."""
    info = TechInfo(name=name, category=category)
    key = name.strip().lower()

    repo = _GITHUB_REPOS.get(key)
    if repo:
        gh = _fetch_github(repo)
        if gh:
            info.github_stars = gh["stars"]
            info.github_language = gh["language"]
            info.github_open_issues = gh["open_issues"]
            info.github_description = gh["description"]
            info.last_updated = gh["updated_at"]
            info.homepage = info.homepage or gh["homepage"]

    npm_name = _NPM_NAMES.get(key, key if key and "." not in key and key[0] != "@" else None)
    if npm_name:
        result = lookup_package(npm_name, registry="npm")
        if isinstance(result, PackageInfo):
            info.registry_version = result.version
            info.registry_downloads = result.downloads
            info.registry_license = result.license
            info.homepage = info.homepage or result.homepage
            info.last_updated = info.last_updated or result.last_updated

    pypi_name = _PYPI_NAMES.get(key)
    if pypi_name and not info.registry_version:
        result = lookup_package(pypi_name, registry="pypi")
        if isinstance(result, PackageInfo):
            info.registry_version = result.version
            info.registry_downloads = result.downloads
            info.registry_license = result.license
            info.homepage = info.homepage or result.homepage
            info.last_updated = info.last_updated or result.last_updated

    return info


def format_tech_info(info: TechInfo) -> str:
    """Render a single TechInfo as indented markdown lines."""
    lines: list[str] = []
    if info.github_stars is not None:
        lines.append(f"   ⭐ {info.github_stars:,} stars")
    if info.github_language:
        lines.append(f"   🔤 Language: {info.github_language}")
    if info.github_open_issues is not None:
        lines.append(f"   🐛 {info.github_open_issues} open issues")
    if info.github_description:
        lines.append(f"   📝 {info.github_description[:200]}")
    if info.registry_version:
        lines.append(f"   📦 v{info.registry_version}")
    if info.registry_downloads:
        lines.append(f"   ⬇️  {info.registry_downloads}")
    if info.registry_license:
        lines.append(f"   📜 {info.registry_license}")
    if info.last_updated:
        lines.append(f"   🕐 Last updated: {info.last_updated[:10]}")
    if info.homepage:
        lines.append(f"   🔗 {info.homepage}")
    return "\n".join(lines) + "\n" if lines else "   No data found.\n"


def compare_tech(
    tech_a: str,
    tech_b: str,
    category: Category = "library",
) -> str:
    """Compare two technologies side-by-side using GitHub and registry data."""
    left = gather_info(tech_a, category)
    right = gather_info(tech_b, category)

    def _fmt(val) -> str:
        if val is None:
            return "—"
        return str(val)

    a_stars = _fmt(f"{left.github_stars:,}" if left.github_stars is not None else None)
    b_stars = _fmt(f"{right.github_stars:,}" if right.github_stars is not None else None)
    a_issues = _fmt(f"{left.github_open_issues:,}" if left.github_open_issues is not None else None)
    b_issues = _fmt(
        f"{right.github_open_issues:,}" if right.github_open_issues is not None else None,
    )

    lines = [
        f"# {tech_a} vs {tech_b}",
        "",
        f"Category: **{category}**",
        "",
        "## Side-by-Side",
        "",
        f"| Dimension | {tech_a} | {tech_b} |",
        "| --- | --- | --- |",
        f"| **GitHub stars** | {a_stars} | {b_stars} |",
        f"| **Language** | {_fmt(left.github_language)} | {_fmt(right.github_language)} |",
        f"| **Version** | {_fmt(left.registry_version)} | {_fmt(right.registry_version)} |",
        f"| **Downloads** | {_fmt(left.registry_downloads)} | {_fmt(right.registry_downloads)} |",
        f"| **License** | {_fmt(left.registry_license)} | {_fmt(right.registry_license)} |",
        f"| **Open issues** | {a_issues} | {b_issues} |",
        "",
    ]

    lines.append("")
    lines.append(f"## {tech_a}")
    lines.append("")
    lines.append(format_tech_info(left))
    lines.append("")
    lines.append(f"## {tech_b}")
    lines.append("")
    lines.append(format_tech_info(right))

    lines.append("---")
    lines.append("")
    lines.append("*Data fetched from GitHub API, npm registry, and PyPI JSON API.*")

    return "\n".join(lines)
