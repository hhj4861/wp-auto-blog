# AI tech series API publication

- Goal: publish reviewed WordPress drafts 1838 (Muse), 1840 (Dots), 1843 (Jev) with their approved distinct covers.
- Owner/scope: this session; only these drafts and three new media uploads. Preserve their body, title, category, tags and slug.
- Base: e9b2db2. Task branch execution only; no main merge requested or performed.
- Credentials: existing GitHub WordPress secrets stay on the runner. No local extraction.
- Done: image bytes and attachment verified, publish status read back, public pages and images checked.
- Verification: targeted mocked transport tests; read-only production preflight; authorized apply; unauthenticated public verification.
- Current: Seven focused tests passed (upload failure, concurrent edits, approved identity, exact image bytes, three-cover publication and idempotent rerun). Production preflight next.

- Production preflight 37434447128 passed. Apply 37434542518 uploaded Muse but held before attachment/publication because encoded file bytes differed. Verify decoded pixels to allow lossless server PNG recompression; reuse deterministic media slug.

- Apply 37434783505 identified exact cause: server resizes 1672x941 PNG to 1600x900 (media 1846). Permit only original or observed dimensions, with pixel RMS <= 8 and visual hash distance <= 3; reject another valid cover.

## Verified publication result

- Ten focused tests passed. Production run 37434956232 succeeded at code ace57c9 on 2026-10-06.
- All three drafts were published; API readback confirmed their reviewed HTML bodies were preserved. Covers: Muse 1846, Dots 1847, Jev 1848.
- WordPress resized each cover to 1600x900. Visual hash distance 0 for all; maximum pixel RMS 1.737.
- Separate unauthenticated requests confirmed HTTP 200 for all pages and all cover images, correct canonical URLs, and actual cover image elements in the public HTML.
- An extra check initially failed because its arbitrary 3500-character threshold was applied to visible text rather than HTML. Investigation found visible text lengths 3069/3095/3449, H2 counts 7/8/8, and intact ending paragraphs. This was a verification-script assumption failure, not truncated publication.
- https://trendpulse.blog/meta-muse-ai-agent-guide/
- https://trendpulse.blog/openai-dots-ai-agent-guide/
- https://trendpulse.blog/typesafe-jev-decision-model-guide/
- Task execution code remains on ops/ai-tech-api-publish-20261006; no main merge and no scheduled-pipeline change.
