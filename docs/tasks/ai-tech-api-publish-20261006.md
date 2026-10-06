# AI tech series API publication

- Goal: publish reviewed WordPress drafts 1838 (Muse), 1840 (Dots), 1843 (Jev) with their approved distinct covers.
- Owner/scope: this session; only these drafts and three new media uploads. Preserve their body, title, category, tags and slug.
- Base: e9b2db2. Task branch execution only; no main merge requested or performed.
- Credentials: existing GitHub WordPress secrets stay on the runner. No local extraction.
- Done: image bytes and attachment verified, publish status read back, public pages and images checked.
- Verification: targeted mocked transport tests; read-only production preflight; authorized apply; unauthenticated public verification.
- Current: Seven focused tests passed (upload failure, concurrent edits, approved identity, exact image bytes, three-cover publication and idempotent rerun). Production preflight next.
