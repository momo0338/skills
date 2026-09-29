---
name: geographic-point-audit
version: 1.0.0
description: Audits and builds geographic point inventories for city guides, family outings, museums, parks, and venue roundups. This skill should be used when collecting locations within an administrative boundary, classifying points as indoor/outdoor, checking official sources, deduplicating sub-venues, measuring prior-content coverage, and validating counts before publication.
license: MIT
agent_created: true
---

# Geographic Point Audit

Build a defensible point inventory without administrative, naming, duplicate-count, coverage, or false-precision errors.

## Workflow

1. **Freeze the scope**
   - Record the administrative boundary, data date, and target content type.
   - Keep geographically adjacent districts out unless the article explicitly uses a metropolitan scope.
   - Define what counts as one point: independent destination, operating hours, and booking rule. Pure scenery inside a scenic area does not count separately; a separately ticketed or independently bookable museum may.

2. **Collect candidates from two evidence lanes**
   - Official government, operator, venue, and authoritative media sources establish existence, location, current operation, and program details.
   - The publisher's already-published content establishes prior coverage only. Scan only published-content directories and exclude drafts, reports, and the inventory being produced.

3. **Resolve identity before classification**
   - Match full names, aliases, and mother/child venue relationships.
   - Open every keyword hit in context. A short alias is not evidence: `白鹭` may refer to a poem or another district's park.
   - Treat titles such as `除了A，看B` as A being supporting context, not a dedicated article.

4. **Separate evidence tiers**
   - `directly publishable`: current operation and key facts confirmed by a current official source.
   - `publish with qualification`: current official source exists but dynamic fields remain unconfirmed.
   - `observation only`: under construction, suspended, no current official source, ambiguous address, or uncertain current operation.
   - Observation-only points never enter a numeric inventory total merely to fill a category.

5. **Classify and deduplicate**
   - Assign exactly one primary class: `indoor` or `outdoor`.
   - Do not count a sub-area twice. Keep one scenic area as one point unless a sub-venue has independent public access and booking rules.
   - A same-name old and new museum during a transition counts as one institution/point until the old site closes; preserve the current entrance in the status field.
   - Keep a named station, bus stop, or route as transportation information, not a separate destination.

6. **Measure prior coverage**
   - Use four levels:
     - `main story`: the point is the article's title/H1 subject.
     - `supporting only`: named in title as contrast, covered as a scenic-area subsection, or only discussed in body.
     - `deleted story`: a dedicated story existed but is no longer online.
     - `zero`: no valid hit in published content.
   - Search display variants (`E³PARK` and `E3PARK`, full legal name and operating name) and verify the article context.

7. **Write a single canonical table**
   - Use one full canonical name everywhere: detailed sections, overview table, title math, and revision notes.
   - Overview-table fields: number, point, primary class, cost basis, suitable age/qualification, prior coverage, verification status.
   - Keep P0 verification issues in a separate table. Dynamic fields such as fees, hours, age limits, booking, and event schedules must never be guessed.

8. **Validate mechanically**
   - Run `scripts/audit_point_inventory.py <markdown-file>`.
   - Assert: frontmatter title equals H1; overview rows are continuous; classes are only indoor/outdoor; section counts equal overview counts; canonical names match; no duplicates; SEO summary is at most 120 characters; title is at most 64 characters.
   - Re-run after every edit. Never update totals by hand.
   - In a section parser, split on exact Markdown heading prefixes such as `## 二、`; do not split on the substring `outdoor`/`indoor`, because the summary heading may contain those words and produce a false zero-row pass.

## Editorial guards

- Treat `儿童友好公园`, `儿童友好生活场景`, `旅游景区`, and administrative labels as separate official systems unless a source explicitly connects them.
- Preserve time qualifiers exactly: `planned`, `will open`, `currently open`, `seasonal`, `under renovation`, `suspended`.
- If a current official page names only part of a claimed total, record the total and the named subset; do not invent the remainder.
- When two official pages conflict by date or batch, keep the conflict visible and do not merge them speculatively.
- Count coverage against published articles, not against the report that lists the coverage.

## Output boundary

Call the result an inventory, mother table, or research draft until field checks, real-world verification, and editorial prose are complete. A verified count does not imply that every point is suitable for children or currently open.

## Resources

- `scripts/audit_point_inventory.py`: deterministic count, naming, class, and title audit.
- `references/evidence-rubric.md`: source hierarchy, coverage rubric, and common traps.
- `references/official-source-patterns.md`: source patterns for park acceptance, operator status, venue transition, and municipal scene lists.
