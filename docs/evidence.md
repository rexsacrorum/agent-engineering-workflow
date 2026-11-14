# Evidence behind the workflow

The [coordination contract](agent-workflow/coordination.md) says when to delegate, to which role and on which tier, and [measurement](agent-workflow/measurement.md) says how to tell whether that pays. This document holds what those rules rest on: published evidence, one measured session, and what was not verified.

"Read by a research pass" means a research subagent read the source and reported the figure, and the author did not open the page again. Treat those figures as less certain than the ones marked as read on the page.

## What the published evidence says

Figures below were read on the linked page on 2026-11-13 unless marked otherwise.

**Multi-agent setups multiply tokens, and coding is a weak fit for parallel writers.**

- Anthropic's research system used about 4× the tokens of a chat as a single agent and about 15× as a multi-agent system. Token usage alone explained 80% of performance variance on one benchmark (BrowseComp). The same post says most coding tasks have fewer truly parallelizable parts than research, and that work where agents share context or depend on each other is a poor fit. ([How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system), June 2025)
- Claude Code's agent teams use roughly 7× the tokens of a standard session when teammates run in plan mode. That figure is for agent teams, not for ordinary subagents. ([Manage costs effectively](https://code.claude.com/docs/en/costs))
- An independent study across 260 configurations found the change against a single agent ranged from +80.8% on decomposable financial reasoning to −70.0% on sequential planning. ([Towards a Science of Scaling Agent Systems](https://arxiv.org/abs/2512.08296), v3, April 2026.) A research pass reported from the full text that every multi-agent architecture scored below the single agent on SWE-bench Verified, and that independent agents amplified errors 17.2× against 4.4× under central coordination; those two figures were not re-checked against the paper body.
- A failure study of seven multi-agent frameworks reports failure rates of 41% to 86.7% and 14 failure modes; the largest are step repetition, not recognising completion and ignoring task requirements. Read from the paper by a research pass, not re-checked. ([Why Do Multi-Agent LLM Systems Fail?](https://arxiv.org/abs/2503.13657))

**What survives the criticism: single-threaded writes, extra readers.**

- Cognition's 2025 position was to avoid multi-agent systems because parallel actors make conflicting implicit decisions. ([Don't Build Multi-Agents](https://cognition.com/blog/dont-build-multi-agents)) Its 2026 follow-up keeps that objection for parallel writers and reports that what works is several agents contributing intelligence "while writes stay single-threaded". Its reviewer finds an average of 2 bugs per PR, about 58% of them severe, and works best when coder and reviewer share no context. Vendor self-report. ([Multi-Agents: What's Actually Working](https://cognition.com/blog/multi-agents-working), April 2026)
- Claude Code's own guidance now lists "use subagents to protect your context window" and "delegate to a subagent for a better answer" among advice to stop following: running out of context is rarely the problem, the same task handed to a subagent does not get a better answer, and each subagent costs extra tokens. It keeps three uses: parallel work, keeping noisy output out of the main conversation, and a reviewer that has not seen how the code was written. ([Best practices](https://code.claude.com/docs/en/best-practices))
- The same documentation says to stay in the main conversation when phases share significant context or the change is quick, and to use a subagent when output is verbose and the work can return a summary. ([Create custom subagents](https://code.claude.com/docs/en/sub-agents))
- No controlled experiment isolating the effect of a fresh-context reviewer was found. The numbers that exist are vendor reports.

**Cheaper models for read-heavy work, a stronger model as an occasional advisor.**

- Anthropic reports Sonnet with an Opus advisor at +2.7 percentage points on SWE-bench Multilingual with 11.9% lower cost per task, and Haiku with an Opus advisor at 41.2% on BrowseComp against 19.7% alone. The footnotes show the compared runs used different prompts and thinking settings, so treat the direction as supported and the size as approximate. ([The advisor strategy](https://claude.com/blog/the-advisor-strategy), April 2026)
- Subagents are meant to return a condensed summary, "often 1,000-2,000 tokens", after using far more internally. Read by a research pass. ([Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents))

**Productivity claims need measurement, because perception is unreliable.**

- In METR's 2025 trial, 16 experienced developers took 19% longer with AI tools while believing they had been 20% faster. METR now says that result no longer reflects current tools, and calls its own 2026 follow-up data unreliable because of selection effects. The lasting lesson is the gap between felt and measured speed. ([METR 2025 study](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/), [2026 update](https://metr.org/blog/2026-02-24-uplift-update/))

## One measured session

One long session on a pre-release prototype, 23 pull requests, main on the top tier, specialists on the strong tier. Token counts were read from the session transcript and its subagent transcripts, deduplicated by message. Dollar figures are list-price equivalents from the [pricing page](https://platform.claude.com/docs/en/about-claude/pricing), not what a subscription charges.

| Who | Agents | Requests | Cache-read tokens | Cache-write tokens | Output tokens | List-price equivalent |
| --- | --- | --- | --- | --- | --- | --- |
| Main | 1 | 1,068 | 523.9M | 2.47M | 1.09M | about $188 |
| Implementer | 14 | 758 | 120.8M | 2.86M | 0.88M | about $65 |
| Reviewer | 8 | 235 | 27.2M | 1.44M | 0.27M | about $22 |
| Architecture | 1 | 24 | 3.1M | 0.18M | 0.02M | about $2.50 |
| Advisor calls | 45 calls from 24 transcripts | 45 | none; 8.3M uncached input | none | 0.59M | about $90 |

What this shows:

- Main accounts for about half of the cost. More than half of main's cost is re-reading its own history: the median request carried about 0.48M input tokens, nearly all of it cached history.
- Advisor calls are about a quarter of the cost. These are the client's advisor tool, called by main and by specialists; each call sends the whole conversation to the top tier uncached, about 185,000 input tokens on average. The first version of this table missed them, because the transcript records them as a separate part of a message; an independent review of the usage script found the gap.
- On the price list used here the top and strong tiers charge the same for a cached read, and the mid tier half of that. So main's long history is not expensive because of main's tier; it is expensive because every request re-reads it. Moving read-heavy work to the mid tier halves the re-read price of that work and removes it from main's history.
- Eight independent reviews cost about 6% of the total, under $3 each, before the advisor calls some of them made. By the session owner's account they found defects before merge, one of them in main's own change.
- The verifier, QA, docs and delivery roles were never called. Main ran 703 shell commands and 74 browser batches itself, and their output stayed in its history for every later request.

What this does not show:

- It is one session with no comparison run. It shows where tokens went, not that another split would have been cheaper.
- The advisor row is priced as uncached top-tier input and output at list price. The client's documentation says each advisor call reads the whole conversation without caching and is billed at the advisor model's rates on API billing; on a subscription it counts toward plan limits or usage credits ([advisor documentation](https://code.claude.com/docs/en/advisor)).
- Cache writes are all priced at the one-hour rate, which overstates subagents: the best-practices page says subagents get a five-minute cache by default.
- The transcript line format is internal to Claude Code and may change between versions. ([Sessions](https://code.claude.com/docs/en/sessions), read by a research pass.)
- Review findings were not counted per reviewer; the list above is from the session owner's recollection. Counting them is the first job of the [measurement loop](agent-workflow/measurement.md).

The cost of keeping output in main can be estimated. Output of size T tokens that stays in main's history is re-read by every later request, so it costs about T × (later requests) × (cache-read price). A subagent pays for its own run once and returns a short report. Delegation wins when the output is large and many requests follow it; it loses for a short check near the end of a session, or when the subagent must first rebuild context main already has.

## Twenty-five sessions

The same count was run over the 25 largest Claude Code sessions on the same machine that had at least $5 of list-price usage. They cover several projects and several months. Sessions on older models are priced at the current rate for the same model family, so the dollar column is approximate. The sessions were chosen by size, which favours long histories.

| Session | List-price equivalent | Main agent | Re-reading, share of main's cost | Advisor calls | Subagents |
| --- | --- | --- | --- | --- | --- |
| 1 | $724 | 96% | 47% | 0% | 4% |
| 2 | $584 | 70% | 57% | 29% | 1% |
| 3 | $442 | 77% | 52% | 18% | 5% |
| 4 | $415 | 92% | 48% | 7% | 1% |
| 5 | $375 | 52% | 55% | 24% | 24% |
| 6 | $279 | 75% | 53% | 24% | 1% |
| 7 | $237 | 96% | 52% | 4% | 0% |
| 8 | $229 | 62% | 59% | 38% | 0% |
| 9 | $213 | 76% | 53% | 21% | 3% |
| 10 | $201 | 96% | 58% | 4% | 0% |
| 11 | $172 | 94% | 40% | 6% | 0% |
| 12 | $171 | 46% | 49% | 18% | 36% |
| 13 | $168 | 13% | 55% | 23% | 64% |
| 14 | $143 | 68% | 54% | 10% | 22% |
| 15 | $132 | 19% | 55% | 24% | 57% |
| 16 | $126 | 83% | 45% | 15% | 2% |
| 17 | $116 | 60% | 51% | 17% | 23% |
| 18 | $107 | 76% | 34% | 0% | 24% |
| 19 | $105 | 69% | 70% | 31% | 0% |
| 20 | $100 | 89% | 56% | 11% | 0% |
| 21 | $95 | 82% | 57% | 18% | 0% |
| 22 | $93 | 89% | 47% | 11% | 0% |
| 23 | $90 | 67% | 60% | 1% | 32% |
| 24 | $89 | 30% | 25% | 32% | 38% |
| 25 | $73 | 58% | 50% | 23% | 19% |

- Re-reading its own history was between 25% and 70% of the main agent's cost, with a median of 53%; in 21 of 25 sessions it was between 45% and 60%.
- The main agent's share of a session ranged from 13% to 96%, advisor calls from 0% to 38% with a median of 18%, and subagents from 0% to 64%.
- The sessions did different work. The table shows where tokens went in each; it does not rank ways of working.

In the session measured in detail, the characters that went into the main agent's history were 42% tool calls, 37% tool output, 14% user messages, system notes and subagent reports, and 7% the agent's own text; screenshots were not counted. A typical implementer in that session read about 250,000 new tokens and handed back a report of about 2,200.

## A knowledge store: what was measured

The same machine's stored sessions were searched for calls to an external knowledge store, a document store reached through an MCP server.

- In the measured session there were 19 calls: 12 writes, 3 reads of a known document, 4 discovery calls and no search.
- Across the stored sessions of all projects there were 563 calls: 319 writes, 147 document reads, 50 searches (49 of them in one project) and the rest discovery.

Knowledge was written far more often than it was looked up. Whether any read changed a decision was not measured, which is why the task log has a field for it. Each write took several tool calls: find the right place, check for an existing note, then write.

## Measuring a workflow: what exists

- The per-task quality counts in the task log are this package's own adaptation. DORA defines its instability measures, change fail rate and rework rate, at the level of deployments ([DORA metrics](https://dora.dev/guides/dora-metrics/), read by a research pass); no published definition was found for a single developer's pull requests.
- Claude Code's OpenTelemetry export has token and cost counters with a `query_source` attribute that separates main from subagents ([Monitoring](https://code.claude.com/docs/en/monitoring-usage), read by a research pass). It needs a collector running. The built-in `/usage` breakdown gives the subagent share with no setup.

## Self-improving harnesses: what exists

- Google Research published [Harness²](https://github.com/google-research/harness2) in October 2026 under Apache 2.0, marked as not an officially supported Google product. It is a framework that edits an agent's harness, re-runs the task and keeps what helped; its README reports gains of up to 11.5 points on one benchmark. It runs OpenCode and Codex, needs benchmark tasks to re-run, and is a research tool, not something to attach to daily work.
- Gemini CLI's experimental [Auto Memory](https://geminicli.com/docs/cli/auto-memory/) is closer in mechanism: it mines past sessions in the background and drafts memory patches and skills that wait in an inbox for approval.
- For Claude Code, `/insights` writes a report on recent sessions including friction points ([Manage costs effectively](https://code.claude.com/docs/en/costs)). Community tools such as [claude-reflect](https://github.com/BayramAnnakov/claude-reflect) and the [Compound Engineering plugin](https://github.com/EveryInc/compound-engineering-plugin) turn corrections or finished tasks into proposed instruction or knowledge changes; a research pass read their READMEs, and none publishes a measured effect.
- The [periodic review](agent-workflow/measurement.md#periodic-review) in this package is the same idea at the smallest size, with approval by a person and a log that can show whether a change helped.

## Reading list

1. [How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) (Anthropic). Where the 4× and 15× figures come from and what they compare; it also says when the extra tokens buy something.
2. [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) (Anthropic). Start with the simplest thing; the named patterns (orchestrator-workers, evaluator-optimizer) give a shared vocabulary for design reviews.
3. [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) (Anthropic). Context is the scarce resource; compaction, notes and subagents are three ways to spend less of it.
4. [Claude Code best practices](https://code.claude.com/docs/en/best-practices) with [subagents](https://code.claude.com/docs/en/sub-agents) and [costs](https://code.claude.com/docs/en/costs). The vendor's current advice, including what it tells people to stop doing. A workflow should not contradict it without a reason.
5. [Don't Build Multi-Agents](https://cognition.com/blog/dont-build-multi-agents) and [Multi-Agents: What's Actually Working](https://cognition.com/blog/multi-agents-working) (Cognition). The strongest opposing view and its own revision a year later: writes single-threaded, readers many.
6. [Towards a Science of Scaling Agent Systems](https://arxiv.org/abs/2512.08296) (Google Research, Google DeepMind, MIT). Independent numbers on when adding agents helps and when it hurts; the answer depends on whether the task decomposes.
7. [Why Do Multi-Agent LLM Systems Fail?](https://arxiv.org/abs/2503.13657) (Cemri et al.). A catalogue of failure modes to check a design against before building it.
8. [Context Rot](https://www.trychroma.com/research/context-rot) (Chroma). Evidence that longer input degrades results even on simple tasks; the case for short reports and fresh contexts. Read by a research pass.
9. [The advisor strategy](https://claude.com/blog/the-advisor-strategy) (Anthropic). Numbers for pairing a cheaper executor with a stronger advisor, with caveats in the footnotes that are worth reading.
10. [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) (Anthropic). How to grade agent work: outcomes over paths, start with a few dozen tasks from real failures. Read by a research pass.
11. [METR's 2025 developer study](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/) and its [2026 update](https://metr.org/blog/2026-02-24-uplift-update/). The sceptical question about productivity, and why felt speed is not evidence.
12. [DORA metrics](https://dora.dev/guides/dora-metrics/) with the [2025 report announcement](https://cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report). The established delivery measures; the 2025 report ties AI adoption to higher throughput and lower stability. Read by a research pass.

How these were checked: items 1, 4, 9, the second part of 5, the abstract of 6 and the first part of 11 were opened for this document and the quoted figures read on the page. Items 2, 3, 7, 8, 10, 12, the first part of 5, the second part of 11 and the author affiliations of 6 were read by a research pass and not opened again.

Also considered: [Harness²](https://github.com/google-research/harness2) for the self-improving idea at research scale, and [Faros's AI Productivity Paradox](https://www.faros.ai/blog/ai-software-engineering) for team-level data on review time growing with output (read by a research pass).
