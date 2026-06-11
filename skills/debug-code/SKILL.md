---
name: debug-code
description: Debug errors, failed commands, test failures, runtime exceptions, wrong output, flaky behavior, regressions, config/import issues, and bug-fix requests using a local-first CLI workflow with Context7, GitHub CLI, and the ddg_search MCP server (10 tools) for external evidence.
---

# Debug Code

## Operating Principle

Treat errors as symptoms until evidence shows the cause. Work from the most concrete signal available: exact command, full output, local code, recent changes, tests, current docs/source for external dependencies, then the smallest fix that explains all observed behavior.

Do not jump straight from an error string to an edit. First reproduce, isolate, explain, then change.

## Tool Priority

Use the best available tool for the evidence needed. Do not block debugging just because a preferred tool is missing.

- **Local CLI first:** `rg`, `rg --files`, `git status`, `git diff`, focused tests, logs, dependency manifests, lockfiles, and local dependency source.
- **Context7:** use for current, version-aware library/framework documentation and code examples when dependency behavior matters.
- **GitHub CLI (`gh`):** use for GitHub-native evidence such as issues, PRs, checks, releases, repo metadata, source files, and API calls from the terminal.
- **ddg_search MCP:** 10 tools organized into three tiers for external evidence. Use the cheapest tool that answers the question.

### ddg_search MCP — Tool Reference

#### Tier 1 — Direct Search & Retrieval (start here)

| Tool | What It Does | When To Use |
|------|-------------|-------------|
| `web_search` | DuckDuckGo web/news search with JSON or markdown output | Broad search for error messages, known bugs, solutions, release notes |
| `search_docs` | DuckDuckGo scoped to a single domain | Targeted search on official docs (e.g. `docs.python.org`, `react.dev`) |
| `fetch_page` | Clean HTML-to-markdown extraction from any URL | Reading docs, changelogs, error pages, issue threads cleanly; supports metadata extraction and table inclusion |

#### Tier 2 — Community & Issue Mining

| Tool | What It Does | When To Use |
|------|-------------|-------------|
| `github_search` | GitHub Issues/PR search via GitHub Search API | Find upstream bug reports, fix PRs, changelog discussions, feature flags, deprecation notices across any repo |
| `hackernews_search` | Hacker News search via Algolia with comment enrichment | Tech community discussions about bugs, regressions, architectural root causes, known workarounds |
| `reddit_search` | Reddit search via RSS + shreddit enrichment | Real-world troubleshooting threads, niche library issues, configuration gotchas |
| `x_search` | X/Twitter search via Bird CLI | Real-time announcements, outage reports, release alerts, short workaround threads |

#### Tier 3 — AI-Powered Synthesis (for complex/composite questions)

| Tool | What It Does | When To Use |
|------|-------------|-------------|
| `groq_analyze_page` | Fetches a URL and runs an AI query against its content | Extracting specific technical details from a long docs page, changelog, or spec without reading the whole thing |
| `groq_research` | Auto-selects search, browsing, and tools to answer a deep question | Multi-source investigation: "What changed between v2 and v3 that could break X?" or "Why is this pattern failing across these three libraries?" |
| `groq_browse` | Interactive multi-page browser via Groq | Navigating documentation sites that require link-following, JS-rendered pages, or multi-step troubleshooting guides |

#### Not Used

`polymarket_search` (prediction markets) — irrelevant for code debugging.

## Tool Sources

- Context7 for current library/framework docs and examples. Source: https://github.com/upstash/context7
- GitHub CLI `gh` for issues, PRs, checks, releases, source/API access. Source: https://cli.github.com/
- ddg_search MCP for web search, docs search, page extraction, community mining, and AI-powered research (10 tools). Source: https://github.com/sydasif/web-search-mcp

## CLI Workflow

### 1. Capture The Failure

- Record the exact command, inputs, environment assumptions, full error output, file paths, line numbers, versions, and current working directory.
- Re-run once when safe to confirm the failure is reproducible. For flaky failures, run enough times to identify the pattern.
- Separate expected behavior from actual behavior in one sentence.
- If the user provided only a fragment, inspect logs/tests/code before asking for more.

### 2. Check Local State First

Use local evidence before external lookup:

- Inspect nearby code, call sites, config, fixtures, generated files, dependency manifests, lockfiles, and recent diffs.
- Prefer fast shell tools: `rg`, `rg --files`, `git diff`, `git status`, targeted test commands, and focused log inspection.
- Read enough context around each relevant symbol to understand the contract, not just the failing line.
- Check local dependency source when available before assuming external behavior.
- Protect unrelated user changes. Do not revert or overwrite changes you did not make.

### 3. Form Testable Hypotheses

Maintain a small hypothesis list:

- What could produce this exact symptom?
- What observation would prove or disprove each candidate?
- Which candidate best explains all evidence, including edge cases?

Prefer experiments that narrow the search space quickly: focused tests, minimal reproduction commands, temporary logging/inspection that can be removed, or reading the implementation path.

### 4. Pull Current External Evidence

Use external sources when the issue depends on dependency, framework, CLI, API, OS, or standards behavior that may have changed, or when local code delegates behavior to something outside the repo.

#### 4a. Dependency & API Docs — Context7
For library/framework docs, APIs, configuration, version-specific examples, and known edge cases.

#### 4b. GitHub-Native Evidence — `gh`
`gh issue list`, `gh issue view`, `gh pr view`, `gh pr checks`, `gh release view`, `gh repo view`, and `gh api` for upstream GitHub issues, PRs, releases, metadata, checks, and raw source.

#### 4c. General Search — Tier 1

| Scenario | Tool | Why |
|----------|------|-----|
| "Does this error message have a known cause?" | `web_search` with the exact error string | Broadest coverage of blog posts, Stack Overflow, docs, forums |
| "What does the official docs say about this API?" | `search_docs` scoped to the project's docs domain | Skips noise from unofficial sources |
| "Read this changelog / issue / PR in full" | `fetch_page` with the URL | Clean extraction without JS or paywalls |

#### 4d. Issue & Community Mining — Tier 2

| Scenario | Tool | Why |
|----------|------|-----|
| "Is there a GitHub issue for this?" | `github_search` with keywords + repo filter | Direct access to upstream bug tracker, fix PRs, and discussion |
| "Has this been discussed on Hacker News?" | `hackernews_search` | Often surfaces deep architectural analysis and workarounds from core devs |
| "What are real users saying about this?" | `reddit_search` for niche/subreddit-specific chatter | Practical troubleshooting, config fixes, version-specific gotchas |
| "Any breaking news about this outage/incident?" | `x_search` for real-time posts | Time-sensitive: service outages, zero-days, urgent releases |

#### 4e. Deep Research — Tier 3

| Scenario | Tool | Why |
|----------|------|-----|
| "What exactly does this 2000-line doc page say about X?" | `groq_analyze_page` with the URL and a specific question | Skips reading the full page; AI extracts just the relevant parts |
| "What changed across versions that could cause this?" | `groq_research` with a question comparing versions | Auto-searches and synthesizes across multiple sources |
| "Walk through this multi-step troubleshooting guide" | `groq_browse` simulating interactive navigation | Handles pages that need clicking through or JS rendering |

Prefer primary sources: official docs, changelogs, release notes, source code, and upstream issues. Use community posts only as leads unless they include reproducible evidence.

### 5. Confirm Root Cause Before Editing

Before making code changes, be able to state:

- The root cause.
- Why the observed failure follows from that cause.
- What evidence ruled out the main alternatives.
- Which behavior the fix must preserve.

If the root cause is still uncertain, keep investigating. If uncertainty remains after reasonable investigation, report the evidence, the uncertainty, and the next best diagnostic step instead of shipping a speculative fix.

### 6. Implement The Smallest Correct Fix

- Fix the cause, not only the immediate symptom.
- Follow the repository's existing style, abstractions, and ownership boundaries.
- Keep changes scoped. Avoid opportunistic refactors unless they are necessary to fix safely.
- For dependency limitations, adapt at your boundary: validate, normalize, wrap, pin, or document behavior in code/tests as appropriate.
- Remove temporary debug prints, probes, and scratch artifacts before finishing.

### 7. Verify The Fix

Verification should match risk:

- Re-run the original failing command or reproduction.
- Run the narrowest relevant test first, then broader tests if the change touches shared behavior.
- Add or update a regression test when the bug is non-trivial, user-facing, shared, or likely to recur.
- Cover edge cases that were part of the root cause.
- Run static checks when the repository has an obvious command for them.
- Use `gh pr checks` or `gh run view` when CI state is part of the failure or verification.

If a verification command cannot be run, say exactly why and what remains unverified.

## Flaky Or Intermittent Failures

For flakiness, do not rely on a single pass:

- Run repeated attempts or targeted subsets to estimate frequency.
- Look for ordering, timing, randomness, shared state, network, timezone, locale, filesystem, cache, and parallelism dependencies.
- Capture seed, timestamps, worker count, and environment details when available.
- Check upstream issues/releases with `github_search`, `gh`, and community search (`hackernews_search`, `reddit_search`) when the flake may come from a dependency or hosted service.
- Prefer deterministic fixes over retries. Retries are acceptable only when the underlying operation is inherently unreliable and the retry policy is bounded and justified.

## Reporting Back

When finished, keep the summary evidence-based:

- Root cause in plain language.
- Files changed and why.
- Verification commands and outcomes.
- External sources used, with the specific tool that found each (e.g., "found via `github_search`", "confirmed on docs via `groq_analyze_page`").
- Remaining risk or unverified areas, if any.
