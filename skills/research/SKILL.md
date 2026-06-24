---
name: research
description: Research any topic — current events, products, people, concepts, comparisons — using Web Search MCP for evidence gathering and structured multi-source synthesis.
---

# Deep Research

## Operating Principle

Research is breadth-first, then depth-first. Start wide to map the landscape, then dive into the highest-signal sources. Do not jump to a single source type and call it done — each platform reveals a different facet of the topic.

Good research answers not just _what_ happened, but _who_ is saying it, _how_ confident the evidence is, and _what_ the competing narratives are.

**Cross-source corroboration:** A claim found in 3+ independent sources is stronger than any single source. Multi-platform coverage is the highest-confidence signal.

**Internalize the research first:** Ground your synthesis in the ACTUAL research content, not your pre-existing knowledge. If sources talk about "ClawdBot" and you assumed "Claude Code", do not conflate them.

---

## Important: What the MCP Handles vs What You Do

This skill uses the `Web Search` MCP server. Search, dedup, clustering, and stats computation, here **you do all that synthesis work manually** as you read tool results.

**The MCP gives you:**

- Search and retrieval across 10 tools covering web, social, academic, and developer platforms
- Clean extracted content from URLs
- Rich engagement data (upvotes, comments, views) from community platforms

**You are responsible for:**

- Running searches sequentially (no engine to fan out in parallel)
- Counting and tracking which claims came from which source
- Spotting patterns and clusters as you read
- Computing stats manually from result sets
- Noticing "X Reply Clusters" in Reddit threads yourself

**Cost of comparison mode:** Comparing 2 entities means roughly 2x the tool calls (~8-12 per entity). Plan your turn budget accordingly. For 3-way comparisons, consider doing a single focused comparison instead of exhaustive per-entity research.

---

## Tool Reference — 10 Web Search Tools

### Tier 1 — Broad Discovery & Reference

| Tool                  | What It Does                                                        | When To Use                                         |
| --------------------- | ------------------------------------------------------------------- | --------------------------------------------------- |
| `search_web`          | DuckDuckGo web/news search                                          | First pass: news, background, official sources      |
| `search_web` (domain) | DuckDuckGo scoped to a domain                                       | Targeted docs: `docs.python.org`, `react.dev`, RFCs |
| `fetch_web_page`      | Clean HTML-to-markdown + Exa fallback for bot-heavy/JS/PDF pages    | Read articles, changelogs, specs, papers            |
| `search_wikipedia`    | Full article text via MediaWiki API                                 | Factual summaries, background research, citations   |
| `search_arxiv`        | Academic paper search w/ Lucene field prefixes                      | Research papers, literature reviews, citations      |

### Tier 2 — Community & Social Signal

| Tool                  | What It Does                             | When To Use                                                 |
| --------------------- | ---------------------------------------- | ----------------------------------------------------------- |
| `search_reddit`       | Reddit via RSS + shreddit enrichment     | Real-user discussions, product feedback, niche opinions     |
| `search_hackernews`   | HN via Algolia + comment enrichment      | Tech debate, architectural analysis, deep critical takes    |
| `search_github`       | GitHub Issues/PR search                  | Upstream discussions, feature requests, deprecation notices |
| `get_github_issue`    | Full GitHub Issue/PR thread with comments | Complete conversation context sorted by reactions            |
| `search_x`            | X/Twitter via Bird CLI                   | Real-time announcements, expert takes, breaking news        |
| `compare_technologies`| Side-by-side comparison via GitHub + registry data | Evaluate tech choices with real metrics                     |

---

## Source Weighting

| Source                          | Signal | Best For                                    |
| ------------------------------- | ------ | ------------------------------------------- |
| Official docs, specs, papers    | ★★★★★  | Ground truth, APIs, specifications          |
| GitHub (code, issues, releases) | ★★★★☆  | Open-source projects, technical evidence    |
| Hacker News comments            | ★★★★☆  | Tech consensus, critical analysis           |
| Web search (blogs, news)        | ★★★☆☆  | Broad coverage, multiple viewpoints         |
| Reddit discussions              | ★★★☆☆  | Real-user opinions, practical experience    |
| X/Twitter                       | ★★☆☆☆  | Real-time signal, expert takes (high noise) |

Cross-platform corroboration beats any single source type. A claim on Reddit + HN + a blog is stronger than a single whitepaper.

---

## OUTPUT CONTRACT

**LAW 1 — Badge on line 1.** `🔍 deep-research · {YYYY-MM-DD}`. One blank line, then report. No title, no preamble.

**LAW 2 — NO em-dashes (`—`) or en-dashes (`–`).** Use `-` (single hyphen with spaces). Everywhere. Exception: quoted content.

**LAW 3 — NO `##` section headers in body.** No `## Key Findings`, no `## Analysis`. Narrative uses **bold-lead-in** paragraphs. Exceptions: comparison mode (see below).

**LAW 4 — Bold-lead-in paragraphs.** Every narrative paragraph begins with `**Headline** - `.

**LAW 5 — Inline markdown links.** `[name](url)` for every citation. Raw URLs never shown. Priority:

- `[@handle](https://x.com/handle)` > `[r/sub](https://reddit.com/r/sub)` > `[channel](url)` > `[HN](url)` > `[publication](url)`
- Never emit broken `[name]()`.

**LAW 6 — NO trailing Sources block.** The `Sources consulted:` list is INSIDE the report. Nothing after the invitation.

---

## Pre-Flight: Keyword Trap Detection

Before any searches, check for these failure classes:

**Class 1 — Demographic shopping:** `gift for 42 year old man` → ask about hobbies/relationship/budget, or reframe to `gifts for men in their 40s` + scope to gift subreddits.

**Class 2 — Numeric keyword trap:** `42` collides with unrelated content (Jackie Robinson, Hitchhiker's). Strip numbers from queries unless load-bearing ("GPT-4" is fine).

**Class 3 — Overly-literal phrasing:** `how to use Docker` → social posts use "my Docker setup", "Docker Compose tip", not tutorial phrasing. Reframe to discussion keywords.

**Class 4 — Generic single noun:** `sneakers`, `coffee`, `bread` → no anchor, pure noise. Ask for specificity.

---

## Resolution Phase

Before community searches, resolve platform-scoped targeting. This is where you do manual lookups that drastically improve signal quality.

**Subreddits:** Run `search_web "{topic} subreddit"` to find 3-5 relevant subreddits. For product/tool topics, also add 2-3 category-peer subs from the table below (where cross-product discussion actually happens):

| Category          | Peer Subs                                         |
| ----------------- | ------------------------------------------------- |
| AI image gen      | `StableDiffusion, midjourney, dalle2, aiArt`      |
| AI video gen      | `aivideo, StableDiffusion, runwayml, singularity` |
| AI music gen      | `SunoAI, udiomusic, aimusic`                      |
| AI coding         | `ChatGPTCoding, LocalLLaMA, singularity`          |
| AI chat models    | `LocalLLaMA, ChatGPT, ClaudeAI, singularity`      |
| SaaS/productivity | `SaaS, productivity, Entrepreneur`                |

**X handles:** For person/product topics, run `search_web "{topic} X handle"` for the primary handle and 1-2 commentators.

**GitHub:** For developer topics, resolve `github.com/{handle}`. For projects, resolve `owner/repo`.

Use these resolved values when calling community search tools (e.g., `search_reddit` with the `subreddits` parameter). Scoped searches produce dramatically better signal than keyword-only searches.

---

## Research Workflow

### Phase 1 — Broad Discovery (Tier 1)

Run 2-3 searches to map the landscape. Vary the angle:

```bash
search_web "{topic} 2026"              # direct
search_web "{topic}" (news mode)        # news
search_web "{topic}" domain="docs.python.org"  # official docs
```

From results, pick 1-2 long-form sources to deep-read later.

### Phase 2 — Community Mining (Tier 2)

Mine 3-4 platforms. Use resolved handles/subreddits/repos to scope. The tool results come with engagement data — use it:

| Platform            | How                            | Look For                                                                    |
| ------------------- | ------------------------------ | --------------------------------------------------------------------------- |
| `search_reddit`     | Topic + `subreddits` parameter | Real experiences, complaints, workarounds. Top comments are highest-signal. |
| `search_hackernews` | Topic + keywords               | The _why_ behind the news. Comments from domain experts.                    |
| `search_github`     | Topic as issue/PR keyword      | Roadmap signals, breaking changes, community wishlists.                     |
| `search_x`          | Topic + resolved handles       | Real-time reactions, expert threads, announcements.                         |

**Per-platform notes (read before searching):**

- **Reddit:** When you see a thread where someone asked for recommendations and multiple independent replies converged on the same answer, note it — this "Reply Cluster" pattern is the strongest form of community endorsement. The `search_reddit` tool returns top comments with scores; read them.
- **HN:** The `search_hackernews` result includes `top_comments` and `comment_insights` fields — these are pre-extracted for you. Use them.
- **GitHub:** `search_github` returns `state` (open/closed), `labels`, `engagement.reactions`, and `top_comments`. Look for closed PRs to see how something was fixed.
- **X:** No engagement enrichment in the current response. Treat X as real-time signal; cross-reference against other sources.

### Phase 3 — Synthesis (You Do This Manually)

After reading all results, answer these questions:

- **Corroborated?** — same claim in 3+ independent sources → high confidence
- **Contradicted?** — sources disagree → note each camp
- **Single-sourced?** — interesting but lower confidence → flag it
- **Missing?** — questions the evidence doesn't answer

---

## Output Format

### General / News

```markdown
🔍 deep-research · 2026-06-10

**{Headline}** - {1-2 sentences}, per [@handle](url)

**{Headline}** - {1-2 sentences}, per [r/sub](url)

**{Headline}** - {1-2 sentences}, per [publication](url)

Patterns from the research:

1. {Pattern} — per [source](url)
2. {Pattern} — per [source](url)
3. {Pattern} — per [source](url)

Gaps & uncertainty:

- {What isn't known or weakly supported}

Sources consulted:

- [name](url)
- [name](url)

---

Some things you could ask next:

- {Specific follow-up based on the most discussed finding}
- {Deeper dive into a contested angle}
```

### Recommendations

Rank by **signal quality**, not mention count. This is the most common failure mode in recommendation research — leading with "Python has 15 mentions" when the actual story is a domain expert switching to Go.

| Signal                                | Weight  | Example                              |
| ------------------------------------- | ------- | ------------------------------------ |
| Practitioner testimony with specifics | Highest | "I use X for Y and here's why"       |
| Expert defection                      | High    | Domain insider publicly switching    |
| Measurable benchmark                  | High    | "43.7% latency win"                  |
| Reasoned comparison                   | Medium  | Side-by-side with tradeoffs          |
| Multiple unaffiliated voices concur   | Medium  | Various people saying the same thing |
| Descriptive mention (exists)          | Low     | "X is a Python framework"            |
| Promotional / bootcamp                | Skip    | "Comment CODE for my course"         |

Lead with the 30-day delta, not the status-quo baseline. A status-quo leader with no new movement is a footer item.

Output:

```markdown
🔍 deep-research · 2026-06-10

Recommended (ranked by signal quality):

**[Pick 1]** - why it's the top recommendation

- Evidence: {specific quote, benchmark, or defection}
- Best for: {use case}
- Voices: {@handles, r/subs}

**[Pick 2]** - ...

**[Pick 3]** - ...

Also mentioned (exists, not specifically recommended): {name} ({why it's a mention, not a pick})

Gaps & uncertainty:

- ...

Sources consulted:

- [name](url)
```

### Comparison (X vs Y)

**Cost warning:** Each entity requires its own Phase 1-2 search cycle. For 2 entities expect ~10-14 tool calls total. Use the subreddits parameter and resolved handles to scope early and avoid wasted searches.

```markdown
🔍 deep-research · 2026-06-10

# {A} vs {B}: What the Research Says

## Quick Verdict

{Thesis sentence. Comparable metrics. Community framing quote.}

## {Entity 1}

Strengths:

- {per [source](url)}
- ...

Weaknesses:

- {per [source](url)}

## {Entity 2}

{Same structure}

## Head-to-Head

| Dimension  | {A} | {B} |
| ---------- | --- | --- |
| What it is | ... | ... |
| Key signal | ... | ... |
| Best for   | ... | ... |

## The Bottom Line

{A} if {use case}. {B} if {use case}.

Sources consulted:

- [name](url)
```

The `## Quick Verdict`, `## {Entity}`, `## Head-to-Head`, `## The Bottom Line` headers are exceptions to LAW 3 — allowed only in comparison mode.

---

## Pre-Presentation Self-Check

1. **Badge on line 1.** Nothing above it.
2. **Bold headlines** on every narrative paragraph.
3. **No em-dashes** — all replaced with `-`.
4. **No `##` headers** in body (comparison mode exempted for the 4 allowed headers).
5. **Inline markdown links** — every name/handle is `[text](url)`. No raw URLs, no `[name]()`.
6. **No trailing Sources block** — `Sources consulted:` is inside the report. Nothing after invitation.
7. **Research grounded in actual sources** — not what you already knew.

Max ONE regeneration. If still broken, emit the best version and note the gap.

---

## Post-Research Mode

After delivering the report, treat yourself as an expert for the rest of the conversation. Do NOT run new searches on the same topic — answer from what you gathered. Only research again if the user asks about a different topic.

---

## Edge Cases

- **Too broad:** Narrow with one clarifying question, or auto-scope to the most common interpretation. Mention the choice.
- **Zero results:** Widen the query. Check for typos. If still empty: "no significant discussion found."
- **Conflicting evidence:** Present both sides with source authority notes. Don't cherry-pick.
- **Breaking news:** Use `search_web` (news mode) + `search_x`. Timestamp everything. Flag volatility.
- **SEO pollution:** Add `-site:spam-site.com` exclusions. Prefer `search_web` with `domain="..."` on known-good domains. Community platforms (Reddit, HN) resist SEO gaming.
