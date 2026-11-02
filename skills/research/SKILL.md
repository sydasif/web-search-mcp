---
name: research
description: Research a topic across many sources and synthesize what the evidence says - current events, products and tools, people, technical concepts, "what are people saying about X", "X vs Y" comparisons, "what's the best Z", recommendations, trend checks, or background before a decision. Use whenever the user wants more than one quick lookup or asks to look into, dig into, compare, survey, or get the landscape on something, even if they don't say "research". Uses web, Reddit, Hacker News, GitHub, X, arXiv, Wikipedia, Techmeme, Digg, Polymarket, and LinkedIn via the OmniSearch MCP, then writes a cited report. Not for fixing bugs (use debug) or fact-checking an existing plan (use review-plan).
---

# Deep Research

## Operating Principle

Research is breadth-first, then depth-first. Map the landscape wide, then read the highest-signal sources in full. Do not jump to one source type and call it done: each platform shows a different facet of the topic.

Good research answers not just *what* happened, but *who* is saying it, *how confident* the evidence is, and *what the competing narratives are*. A claim found in 3+ independent sources is stronger than any single source.

**Ground the synthesis in what the sources actually say, not in what you already believed.** If sources use a name or term you would have mapped to something you know, check before assuming they mean the same thing. Conflating look-alike names is the commonest way research goes wrong.

## Tools

All tools come from the OmniSearch MCP server. Use the bare names; the client may add a server or plugin prefix. The server does the fetching; you do the reading, counting which claims come from which source, spotting clusters, and computing any stats from the results by hand.

Independent calls can run in parallel. Keep batches modest (DuckDuckGo rate-limits; a 429 means retry later, not "nothing found").

| Topic type | Tool | Notes |
| --- | --- | --- |
| Anything: first pass | `search_web` | Default `max_results` is 5; use 8-10 for research. `search_type="news"` for news, `time_range` ("d", "w", "m", "y") for recency, `domain` to scope to one site |
| Read a source in full | `fetch_page` | Needed for every long-form source you plan to cite in depth |
| Background, definitions | `search_wikipedia` | Full text of the top article |
| Academic work | `search_arxiv` | Field prefixes: `ti:`, `au:`, `abs:`, `cat:` |
| Real-user experience, opinions | `search_reddit` | Use `subreddits=[...]` |
| Tech debate, expert critique | `search_hackernews` | `from_date`/`to_date` only work together |
| Open-source projects, roadmaps | `search_github`, `get_github_issue` | Needs `GITHUB_TOKEN` or `gh`; title-only search, sorted by reactions |
| Real-time reaction, announcements | `search_x` | Needs credentials; high noise |
| AI industry discourse | `search_digg` | Needs `digg-pp-cli` on PATH |
| Tech industry news | `search_techmeme` | Needs `techmeme-pp-cli` on PATH |
| Forecasts, real-money odds on events | `search_polymarket` | |
| People, companies, jobs | `search_linkedin` | Poorly indexed |
| Trim a large pile of snippets | `rerank_results` | Token-overlap scoring only |

If a credential- or CLI-gated tool errors, say so in "Gaps & uncertainty" and continue with the others; do not silently drop the platform.

## Source Weighting

| Source | Signal | Best for |
| --- | --- | --- |
| Official docs, specs, papers (arXiv) | ★★★★★ | Ground truth, APIs, specifications |
| GitHub (code, issues, releases) | ★★★★☆ | Open-source projects, technical evidence |
| Hacker News comments | ★★★★☆ | Tech consensus, critical analysis |
| Techmeme / reputable news | ★★★★☆ | What happened and when |
| Web search (blogs, news) | ★★★☆☆ | Broad coverage, multiple viewpoints |
| Reddit discussions | ★★★☆☆ | Real-user opinions, practical experience |
| Polymarket | ★★★☆☆ | Crowd probability on a dated, resolvable event |
| Wikipedia | ★★★☆☆ | Orientation; follow its citations for anything load-bearing |
| Digg clusters, X/Twitter | ★★☆☆☆ | Real-time signal, expert takes (high noise) |

Cross-platform corroboration beats any single source type. A claim on Reddit, HN, and a blog is stronger than one whitepaper.

## Pre-Flight: Keyword Trap Detection

Before any searches, check for these failure classes:

**Class 1 - Demographic shopping:** `gift for 42 year old man` -> ask about hobbies, relationship, and budget, or reframe to `gifts for men in their 40s` and scope to gift subreddits.

**Class 2 - Numeric keyword trap:** a bare number collides with unrelated content. Strip numbers from queries unless load-bearing ("GPT-4" is fine).

**Class 3 - Overly literal phrasing:** `how to use Docker` -> social posts say "my Docker setup" or "Docker Compose tip", not tutorial phrasing. Reframe to discussion keywords.

**Class 4 - Generic single noun:** `sneakers`, `coffee`, `bread` have no anchor and return noise. Ask for specificity.

## Resolution Phase

Before community searches, resolve platform-scoped targets. A few lookups here sharply improve signal.

**Subreddits:** run `search_web` for `{topic} subreddit` to find 3-5 relevant subreddits. For product or tool topics, add 2-3 category-peer subs, where cross-product discussion actually happens:

| Category | Peer subs |
| --- | --- |
| AI image gen | `StableDiffusion, midjourney, dalle2, aiArt` |
| AI video gen | `aivideo, StableDiffusion, runwayml, singularity` |
| AI music gen | `SunoAI, udiomusic, aimusic` |
| AI coding | `ChatGPTCoding, LocalLLaMA, singularity` |
| AI chat models | `LocalLLaMA, ChatGPT, ClaudeAI, singularity` |
| SaaS/productivity | `SaaS, productivity, Entrepreneur` |

**X handles:** for person or product topics, `search_web` for `{topic} X handle` to find the primary handle and 1-2 commentators.

**GitHub:** for developer topics, resolve the `owner/repo` and scope with `repo:owner/name` inside the `search_github` query.

## Research Workflow

### Phase 1 - Broad discovery

Run 2-3 `search_web` calls with different angles, using `max_results` of 8-10:

- the topic directly, with `time_range` if recency matters (do not hard-code a year into the query);
- the topic with `search_type="news"`;
- the topic scoped with `domain` to the official site or docs, when one exists.

For academic or background topics, add `search_arxiv` or `search_wikipedia` here. For AI or tech-industry topics, add `search_techmeme` and `search_digg`. For questions about future events, add `search_polymarket`.

### Phase 2 - Deep read

Pick the 2-4 strongest long-form sources from Phase 1 (official docs, a substantive article, a paper, a changelog) and read them with `fetch_page`. Snippets are not enough to characterize a source; this step is where you find the specifics that make a report useful.

### Phase 3 - Community mining

Mine 3-4 platforms with the resolved subreddits, handles, and repos:

| Platform | How | Look for |
| --- | --- | --- |
| `search_reddit` | Topic + `subreddits` | Real experiences, complaints, workarounds. Top comments are highest signal |
| `search_hackernews` | Topic + keywords | The *why* behind the news; comments from domain experts |
| `search_github` | Short topic keywords, `repo:` scoping | Roadmap signals, breaking changes, community wishlists |
| `search_x` | Topic + resolved handles | Real-time reactions, expert threads, announcements |

Per-platform notes:

- **Reddit:** when a recommendation thread has multiple independent replies converging on the same answer, note it. This "Reply Cluster" is the strongest form of community endorsement. Read the top comments and their scores.
- **HN:** results carry `top_comments` and `comment_insights`; use them before fetching threads.
- **GitHub:** results carry `state`, `labels`, `engagement.reactions`, and (for top hits) `top_comments`. Closed PRs show how something was fixed. Use `get_github_issue` for a full thread.
- **X:** results carry engagement (likes, retweets, replies) but it is a noisy, short-horizon signal. Corroborate against other sources.

### Phase 4 - Synthesis

After reading everything, answer:

- **Corroborated?** Same claim in 3+ independent sources: high confidence.
- **Contradicted?** Sources disagree: note each camp and its authority.
- **Single-sourced?** Interesting but lower confidence: flag it.
- **Missing?** Questions the evidence does not answer.

---

## Output Contract

Every report follows these rules; the templates below already comply.

**LAW 1 - Badge on line 1.** `🔍 deep-research · {YYYY-MM-DD}` using today's actual date, then one blank line, then the report. No title and no preamble before or after the badge. Never copy a date from an example.

**LAW 2 - No em-dashes (`—`) or en-dashes (`–`).** Use ` - ` (hyphen with spaces) everywhere in your output. Exception: quoted content.

**LAW 3 - No `##` section headers in the body.** Narrative uses bold-lead-in paragraphs. Exception: comparison mode, which allows the four headers it names.

**LAW 4 - Bold-lead-in paragraphs.** Every narrative paragraph begins `**Headline** - `.

**LAW 5 - Inline markdown links.** `[name](url)` for every citation, never raw URLs, never an empty `[name]()`. Prefer `[@handle](https://x.com/handle)`, then `[r/sub](https://reddit.com/r/sub)`, then `[channel](url)`, `[HN](url)`, `[publication](url)`.

**LAW 6 - Sources inside, invitation last.** `Sources consulted:` comes before the follow-up invitation, and nothing comes after the invitation. No separate sources block anywhere else.

## Output Format

### General / News

```markdown
🔍 deep-research · {YYYY-MM-DD}

**{Headline}** - {1-2 sentences}, per [@handle](url)

**{Headline}** - {1-2 sentences}, per [r/sub](url)

**{Headline}** - {1-2 sentences}, per [publication](url)

Patterns from the research:

1. {Pattern} - per [source](url)
2. {Pattern} - per [source](url)
3. {Pattern} - per [source](url)

Gaps & uncertainty:

- {What isn't known or is weakly supported, and any tool that was unavailable}

Sources consulted:

- [name](url)
- [name](url)

---

Some things you could ask next:

- {Specific follow-up based on the most discussed finding}
- {Deeper dive into a contested angle}
```

### Recommendations

Rank by **signal quality**, not mention count. The common failure is leading with "Python has 15 mentions" when the real story is a domain expert switching to Go.

| Signal | Weight | Example |
| --- | --- | --- |
| Practitioner testimony with specifics | Highest | "I use X for Y and here's why" |
| Expert defection | High | Domain insider publicly switching |
| Measurable benchmark | High | "43.7% latency win" |
| Reasoned comparison | Medium | Side-by-side with tradeoffs |
| Multiple unaffiliated voices concur | Medium | Various people saying the same thing |
| Descriptive mention (exists) | Low | "X is a Python framework" |
| Promotional / bootcamp | Skip | "Comment CODE for my course" |

Lead with what changed recently, not the status-quo baseline. A status-quo leader with no new movement is a footer item.

```markdown
🔍 deep-research · {YYYY-MM-DD}

Recommended (ranked by signal quality):

**{Pick 1}** - why it's the top recommendation

- Evidence: {specific quote, benchmark, or defection}
- Best for: {use case}
- Voices: {@handles, r/subs}

**{Pick 2}** - ...

**{Pick 3}** - ...

Also mentioned (exists, not specifically recommended): {name} ({why it's a mention, not a pick})

Gaps & uncertainty:

- ...

Sources consulted:

- [name](url)

---

Some things you could ask next:

- {Follow-up}
```

### Comparison (X vs Y)

**Cost:** each entity needs its own Phase 1-3 cycle, so two entities take roughly 10-14 tool calls. For three or more, offer one focused comparison instead of exhaustive per-entity research. Scope early with `subreddits` and resolved handles to avoid wasted searches.

The four headers `## Quick Verdict`, `## {Entity}`, `## Head-to-Head`, and `## The Bottom Line` are the only `##` headers allowed (an exception to LAW 3). There is no separate title line, so LAW 1 holds.

```markdown
🔍 deep-research · {YYYY-MM-DD}

## Quick Verdict

{Thesis sentence. Comparable metrics. Community framing.}

## {Entity 1}

Strengths:

- {claim}, per [source](url)

Weaknesses:

- {claim}, per [source](url)

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

---

Some things you could ask next:

- {Follow-up}
```

---

## Pre-Presentation Self-Check

Check once, fix what fails, then deliver:

1. Badge on line 1 with today's date; nothing above it.
2. Bold headline on every narrative paragraph.
3. No em-dashes or en-dashes anywhere in the output (templates included).
4. No `##` headers outside comparison mode.
5. Every name or handle is an inline `[text](url)` link; no raw URLs, no `[name]()`.
6. `Sources consulted:` present, followed by the invitation, with nothing after it.
7. Claims trace to sources you actually retrieved, not to prior knowledge.

If a rule truly cannot be met, deliver the best version and note the gap in one line.

---

## After the Report

Answer follow-up questions on the same topic from the evidence you already gathered, and say when something falls outside it. Run new searches when the user asks about a different topic, asks for fresher data, or asks about a gap you flagged. Do not re-run the whole workflow for a clarifying question.

---

## Edge Cases

- **Too broad:** narrow with one clarifying question, or auto-scope to the most common interpretation and say which you chose.
- **Zero results:** widen the query and check for typos. If still empty, say "no significant discussion found" rather than implying the thing does not exist.
- **Conflicting evidence:** present both sides with source authority notes. Do not cherry-pick.
- **Breaking news:** `search_web` with `search_type="news"` and a short `time_range`, plus `search_x`. Timestamp everything and flag volatility.
- **SEO pollution:** scope `search_web` with `domain` to known-good sites. With `provider="ddg"` you can add `-site:spam-site.com` exclusions (not supported on Exa). Community platforms (Reddit, HN) resist SEO gaming.
