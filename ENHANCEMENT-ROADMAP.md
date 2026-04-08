# SEO Agent — Enhancement Roadmap & Implementation Plan
**For Jereme's reference — NOT part of Claude Code CLAUDE.md**
These are human-facing instructions for improving the automation scripts.

---

## SCRIPT ENHANCEMENT ROADMAP (Priority Upgrades)

These are specific improvements to your existing scripts that will directly increase rankings. No new scripts needed — just upgrades to what you have.

### Enhancement 1: `cluster_planner.py` — Add Fan-Out + GEO + NeuronWriter (HIGH IMPACT)

**Current state**: 6 clusters, 31 articles defined. Uses Claude for article generation. Does NOT use geo_optimize.py, NeuronWriter, Crawl4AI, or fan-out logic.

**Upgrades needed**:
```
A) Integrate geo_optimize.py into article generation prompts:
   - Import: from geo_optimize import get_geo_prompt_block, get_speakable_schema
   - Append get_geo_prompt_block(keyword) to every Claude prompt
   - Add Speakable schema to every generated article
   → Impact: Every cluster article becomes AI-citation-ready

B) Add fan-out sub-query mapping per cluster:
   - Before building a cluster, simulate the pillar keyword through Claude
   - Ask: "What 8-12 sub-queries would Google generate for: [keyword]?"
   - Map each sub-query to an existing or new cluster article
   - Flag gaps where no article answers a sub-query
   → Impact: Full fan-out coverage = higher AI Overview citation rate

C) Integrate NeuronWriter scoring:
   - Import: from neuron_seo import get_neuron_recommendations
   - Before generating each article, fetch NeuronWriter recs for the target keyword
   - Inject NLP terms and entity requirements into the Claude prompt
   - Score output and iterate if below 80/100
   → Impact: Better on-page optimization for traditional SERP rankings

D) Add Crawl4AI competitor gap check:
   - Before building a cluster, crawl top 3 competitors for the pillar keyword
   - Extract their subtopic coverage
   - Compare against your cluster articles
   - Add any missing subtopics as new cluster articles
   → Impact: Ensures your cluster is more comprehensive than competitors
```

### Enhancement 2: `gap_analysis.py` — Add Fan-Out + Competitor Crawling (HIGH IMPACT)

**Current state**: Pulls keywords from NeuronWriter + GSC. Analyzes gaps with Claude. Adds to content queue. Does NOT use fan-out, Crawl4AI, or geo_optimize.

**Upgrades needed**:
```
A) Add fan-out discovery as a keyword source:
   - For each seed keyword, simulate fan-out through Claude
   - Capture the 8-12 sub-queries as new keyword candidates
   - Check which sub-queries already have content (via content-registry.json)
   - Flag uncovered sub-queries as HIGH priority gaps
   → Impact: Discovers keywords that keyword tools miss (95% of fan-out phrases show zero volume)

B) Add Crawl4AI competitor scraping:
   - Crawl top 5 competitor sites for each seed keyword
   - Extract their H2 subtopics, FAQ questions, and content themes
   - Compare against your existing content
   - Generate gap report: "Competitor X covers [topic] — you don't"
   → Impact: Data-driven content gaps, not guesswork

C) Add priority scoring to gap output:
   - Score each gap by: estimated volume × (1/difficulty) × fan-out coverage weight
   - Sort queue by priority score, not just chronological
   - Tag each gap with its parent cluster for organized publishing
   → Impact: Publish highest-value content first instead of random order

D) Integrate geo_optimize.py into gap briefs:
   - When adding gaps to content-queue.json, include GEO prompt block
   - So when scheduler.py picks up the article, it's already GEO-optimized
   → Impact: Every gap-fill article is AI-citation-ready from day one
```

### Enhancement 3: `freshness_updater.py` — Add Performance-Based Refresh (MEDIUM IMPACT)

**Current state**: Updates dates, year references, schema dateModified, bonus amounts, copyright. Does NOT check GSC performance, NeuronWriter scores, or trigger content rewrites.

**Upgrades needed**:
```
A) Add GSC-driven decay detection:
   - Connect to GSC API (already have google-indexing-key.json)
   - Pull clicks/impressions for each page over last 90 days
   - Flag pages with >20% traffic decline as "decaying"
   - Flag pages that dropped >5 positions for their primary keyword
   - Prioritize these for refresh over simple date bumps
   → Impact: Fix pages losing rankings before they fall off page 1

B) Add content quality refresh (not just date bumps):
   - For decaying pages, don't just update the date — regenerate key sections
   - Use Claude to rewrite the atomic answer block with fresh data
   - Update comparison tables with current operator data from content-registry.json
   - Add any new FAQ questions that competitors now answer
   → Impact: Real content improvement, not fake freshness signals

C) Add NeuronWriter re-scoring:
   - Re-score existing pages against current NeuronWriter recommendations
   - Flag pages that score below 70/100 (recommendations change as SERPs evolve)
   - Generate specific optimization suggestions: missing NLP terms, entity gaps
   → Impact: Pages stay optimized as competition changes
```

### Enhancement 4: Content Queue — Add Smart Prioritization (MEDIUM IMPACT)

**Current state**: 43 pending articles. Published chronologically (by publish_date). No priority scoring, no cluster tagging, no volume/difficulty data.

**Upgrade the queue structure** from:
```json
{
  "topic": "...",
  "slug": "...",
  "keywords": ["..."],
  "publish_date": "2026-04-07",
  "status": "pending"
}
```
To:
```json
{
  "topic": "...",
  "slug": "...",
  "keywords": ["..."],
  "publish_date": "2026-04-07",
  "status": "pending",
  "priority": "high",
  "cluster": "mobile-money",
  "source": "gap_analysis",
  "fan_out_parent": "best online casino papua new guinea",
  "estimated_volume": 320,
  "difficulty": "low",
  "geo_optimized": true
}
```
**Then update `scheduler.py`** to:
- Sort by priority before publish_date
- Ensure cluster articles publish in sequence (pillar first, spokes after)
- Log which articles were published and their source
→ Impact: Highest-value content publishes first. Cluster integrity maintained.

### Enhancement 5: `add_content.py` — Add GEO + Atomic Answers (HIGH IMPACT)

**Current state**: Generates articles, auto-interlinks, updates registry and sitemap. Does NOT use geo_optimize.py, atomic answer blocks, or fan-out awareness.

**Upgrades needed**:
```
A) Integrate geo_optimize.py:
   - Import get_geo_prompt_block and get_speakable_schema
   - Append GEO prompt block to every article generation prompt
   - Add Speakable schema to every generated article
   → Impact: Every new article is AI-citation-ready

B) Enforce atomic answer blocks:
   - Add to the Claude prompt: "Include a 40-60 word atomic answer block
     within the first 300 words AND after each H2"
   - These are the passages AI systems extract and cite
   → Impact: Direct increase in AI Overview citations

C) Add fan-out awareness:
   - Before generating, check if this article's topic matches any known
     fan-out sub-query from the parent keyword
   - If yes, ensure the article directly answers that sub-query in the
     first paragraph with definitive language
   → Impact: Content designed for the hidden query layer
```

---

### Implementation Priority Order

| Order | Enhancement | Script | Effort | Impact |
|-------|-----------|--------|--------|--------|
| 1 | Add GEO + atomic answers to content generation | `add_content.py` | 30 min | **HIGH** — every new article becomes AI-citable |
| 2 | Add fan-out mapping to cluster planner | `cluster_planner.py` | 1 hour | **HIGH** — fills the hidden query layer |
| 3 | Add fan-out as keyword source in gap analysis | `gap_analysis.py` | 1 hour | **HIGH** — discovers keywords tools miss |
| 4 | Add smart priority to content queue | `content-queue.json` + `scheduler.py` | 30 min | **MEDIUM** — publish highest-value content first |
| 5 | Add GSC decay detection to freshness updater | `freshness_updater.py` | 1 hour | **MEDIUM** — catch ranking drops before page 2 |
| 6 | Add NeuronWriter to cluster planner | `cluster_planner.py` | 30 min | **MEDIUM** — better on-page optimization |
| 7 | Add Crawl4AI competitor gaps to gap analysis | `gap_analysis.py` | 1 hour | **MEDIUM** — data-driven gaps |
| 8 | Add content quality refresh to freshness updater | `freshness_updater.py` | 1 hour | **LOW** — real refresh vs date bumps |

Start with 1-3. Those three changes alone will significantly increase your AI visibility and content quality. The rest can wait.

Those three changes alone will significantly increase your AI visibility and content quality. The rest can wait.
