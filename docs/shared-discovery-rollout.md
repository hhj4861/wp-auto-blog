# Shared discovery operational wiring — 2026-10-03

PR #78 is merged; production is **not enabled** yet. The common service image failed its real HTTPS probe because Python had no CA bundle. The commerce follow-up fixes trust and adds scoped Cloudflare delivery. This follow-up completes the blog opt-in and a no-publication acceptance workflow.

## Credential boundaries

`CAK_DISCOVERY_BLOG_KEY` is held in the existing Cloudflare Secrets Store. Its broker binding is `SS_DISCOVERY_BLOG_KEY`. No new GitHub long-lived secret is needed. GitHub OIDC can retrieve this key only from `hhj4861/wp-auto-blog` (repository ID 1126598753, owner ID 71001056), main, GitHub-hosted runner, and exact `blog-keyword-select.yml` or `shared-discovery-check.yml` paths. Forks, PRs, arbitrary workflows and reusable-workflow substitutions are rejected. Broker flag `GITHUB_BLOG_DISCOVERY_ENABLED=true` is required after the bindings exist. The existing dedicated Codex restore/refresh/persist lifecycle remains unchanged; this change does not migrate its token.

`load_discovery_credentials.py` validates/masks the OIDC response and only accepts the blog key. It exports that key and a stable SHA-256 service subject to the ephemeral runner environment. No keys are written to reports or artifacts. Redirects and invalid key names/values fail closed. Rotation is read on each job; never fall back to an old key on broker failure.

## Enable in order

1. Merge the companion commerce production-wiring fix, provision all distinct discovery platform keys in Cloudflare, and deploy the CA-fixed discovery service and reviewed broker/edge. Inject only the blog key into this scope; the discovery container receives the full platform map plus dedicated limited Jev key and existing Naver key.
2. Enable the broker's blog discovery policy. Run **Shared Discovery Live Check** on main with one category. This makes one start/claim/generation/completion sequence, at most four search attempts and three Jev attempts, and no WordPress call, report save, publication or automatic retry. Existing shared concurrency prevents racing other Codex refresh jobs. Logs contain request ID, state/count and usage only. An all-held outcome is a visible failed acceptance check, not proof of fact checking.
3. Inspect accepted primary evidence and server/provider usage; then set this repository's nonsecret `DISCOVERY_ENABLED=1` variable. Only the category selection workflow is wired here. A different direct runtime of the general LLM collector still needs its own DISCOVERY_URL/API_KEY/SUBJECT env configuration; do not claim all auto-post entry points switched by this flag.

Roll back deliberately by setting `DISCOVERY_ENABLED=0` (old category selection remains available). Do not erase request history or rotate native Codex tokens. Revoke/replace discovery keys through Cloudflare and the server platform map together; no raw key in GitHub CLI arguments/logs. Live checking is pending approval of the companion fixes; fixture tests do not prove production quality.

Validation: 620 related fixture tests passed (618 in the combined run; two existing Reddit fixtures rechecked after installing their optional `praw` test dependency). The OIDC loader's 13 cases cover scope, redirect prevention, response-key injection, invalid runtime and unavailable broker. Both workflow YAML files parsed successfully. No live model call or WordPress publication was made by these tests.
