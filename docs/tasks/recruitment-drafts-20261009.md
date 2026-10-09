# Recruitment draft completion — 2026-10-09

- Goal: create and review the two requested recruitment drafts; no public publication.
- Owner/scope: invoking Codex; KPF draft 1894 and SK draft 1897 only.
- Base: a8fa472. Dedicated operations branch, no main merge authorized or needed to execute the existing manual workflow on this branch.
- Creation: KPF run 37929040098; SK run 37929043566. Both saved as drafts. SK passed source/quality review.
- KPF review: replace four unsupported notice links, four visible application placeholders (plus FAQ text), and the weakened cancellation condition. Source: JOB-ALIO idx=305752 and https://clothing.snu.ac.kr/채용/?mod=document&uid=10413 (application URL verified from the page).
- Done criteria: exact original checksum and draft identity required, conflict recheck, content-only update, authenticated readback preserving status/slug/date/metadata/media.
- Checks/result: 5 unit tests passed; exact real draft checksum matched; four application links and FAQ JSON verified in memory; real correction pending. No credentials printed or copied.
- Next: test, commit/push task branch, run scoped workflow, inspect readback evidence.
