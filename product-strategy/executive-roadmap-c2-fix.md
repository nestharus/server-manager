# Banned Sentence Openers Fix Report: Executive Roadmap

## Scope

**Concern fixed:** Banned sentence-initial openers (But, And, So, Or, Still, Yet, However, Therefore)
**Instances found:** 2
**Instances fixed:** 2
**Instances skipped:** 0

Scan covered: line starts (after bullets, headings, paragraph breaks) and mid-paragraph occurrences after `.`/`!`/`?`. Both hits were mid-paragraph.

## Sample Fixes

### Instance 1 (line 601, VS-012 Pain severity)
**Before:** `The gap analysis explicitly calls out missing waitlist handling. However, communities work around this with DMs for interviews and informal tracking for waitlists.`
**After:** `The gap analysis explicitly calls out missing waitlist handling. Communities, however, work around this with DMs for interviews and informal tracking for waitlists.`
**Technique:** Moved "however" from sentence-initial to mid-sentence interjection. Preserves the contrast between the market gap and community workaround without violating the ban on starting a sentence with "However".

### Instance 2 (line 630, VS-017 Pain severity)
**Before:** `provisioning, archival, and lifecycle governance are missing even in premium suites. But the market signal is moderate. Only two sources directly evidence the gap.`
**After:** `provisioning, archival, and lifecycle governance are missing even in premium suites. The market signal is moderate; only two sources directly evidence the gap.`
**Technique:** Dropped "But" and fused the two sentences with a semicolon. The second clause ("only two sources...") now serves as the qualifying evidence for the moderate signal, which implicitly carries the contrast with the prior claim about the gap being under-monetized.

## Major Changes Flag

- [ ] Moved a section
- [ ] Rewrote more than 30% of a section
- [ ] Changed the narrative arc
- [ ] Added or removed a section

No major changes. Two local rewrites, both within single bullets inside existing subsections. No restart trigger.

## Known Remaining Issues

- Instance 2 introduces a semicolon to fuse the "moderate signal" claim with its evidence. A reviewer may prefer a period split with a different connective; the semicolon was chosen because the second clause directly substantiates the first rather than making a separate claim.
- No em dashes were introduced. Factual content, citations, and markdown structure were preserved verbatim apart from the two edits above.
