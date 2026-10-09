# Recruitment draft completion — 2026-10-09

- Goal: create and review the two requested recruitment drafts; no public publication.
- Owner/scope: invoking Codex; KPF draft 1894 and SK draft 1897 only.
- Base: a8fa472. Dedicated operations branch, no main merge authorized or needed to execute the existing manual workflow on this branch.
- Creation: KPF run 37929040098; SK run 37929043566. Both saved as drafts. SK passed source/quality review.
- KPF review: replace four unsupported notice links, four visible application placeholders (plus FAQ text), and the weakened cancellation condition. Source: JOB-ALIO idx=305752 and https://clothing.snu.ac.kr/채용/?mod=document&uid=10413 (application URL verified from the page).
- Done criteria: exact original checksum and draft identity required, conflict recheck, content-only request, authenticated readback preserving draft status/slug/metadata/media. WordPress may refresh an unpublished draft timestamp on save; see actual result below.
- Checks: 5 unit tests passed; exact real draft checksum matched; four application links and FAQ JSON verified in memory. No credentials printed or copied.
- Actual result: repair run 37930581382 (code 03fe2e5) applied the correction. Its strict date-preservation assertion failed after the write because WordPress advanced draft date/date_gmt from 2026-10-09T12:22:53 to 2026-10-09T12:31:28. No retry was made.
- Independent artifact verification (11615638783): authenticated after.json is draft 1894 and its raw content exactly matches proposed.html, SHA-256 9836163eba05101369e5b1f170852097814860a7edd24fbdea1580029020ae40. ID/status/slug/title/excerpt/featured_media/categories/tags/meta are unchanged. Four application anchors, corrected notice links and cancellation statement, and FAQ JSON all verified. Derived Yoast output and timestamps updated with the body. The workflow remains marked failure; this is not reported as a successful workflow.
- SK authenticated readback: inspection run 37930241189, artifact 11615474390 confirms draft 1897, title “2026 도시가스 대졸 신입 채용: 코원·충청·강원·전남 비교”, featured media 1896. Source/quality review passed in creation run; full body inspected against the selected official notices.
- Current result: both requested drafts are saved on WordPress and unpublished. No browser login was required. The one-off operation is already applied; do not rerun (original checksum guard intentionally rejects a second write). Automation code remains only on the task branch; no main merge.
- Next: user can review the drafts; public publication is outside this draft-creation operation.
