# Common Jev topic discovery

Implementation branch; not enabled in production. The server and contract live in `hhj4861/commerce-automation-kit/services/topic-discovery/README.md` (discovery-v1). Selection/search/rubric/history decisions execute there; this repository contains a thin Python transport and uses the existing private Codex subscription for drafting only.

Enable only after deploying and validating that shared service. Server-only settings: `DISCOVERY_ENABLED=1`, `DISCOVERY_URL=https://<shared-host>/discovery`, distinct blog `DISCOVERY_API_KEY`, stable provisioned `DISCOVERY_SUBJECT` (64 hex). Keep the existing `BLOG_CODEX_HOME` and `BLOG_CODEX_MODEL`. No token copy or API-key billing fallback is introduced.

Set `DISCOVERY_REQUEST_ID` for manual runs; scheduled execution may use `GITHUB_RUN_ID`. A stable category-specific request key is derived from it. A retry does not create another generation claim; use a new run ID only for an intentional new recommendation. For general collection, optionally set `DISCOVERY_CATEGORY`. Use process TMPDIR under the approved artifact root.

`market_topics.select_category` requests verified server keywords first, then retains the existing exact-keyword measured-demand, source, article-scope and publication gates. Related keywords, YouTube imports, CAK imports and local expansion cannot silently replace the shared shortlist in enabled mode. Additional verification can remove a candidate; it cannot promote a server-held candidate. General `TrendDetector.collect_with_llm` uses the same service. Its score is 0 (unmeasured), not an invented popularity score.

The server stores its own recent scoped accepted history and merges bounded client history. Existing titles/registry are supplementary; empty client history cannot erase server history. A service/connection failure or zero accepted candidates fails visibly, with no local legacy fallback. Disabling the feature is a deliberate deployment rollback, not an automatic response to errors.

Evidence currently consists of official search-API excerpts. The server reports `factChecked:false` and `requiresHumanReview:true`; a Jev pass is a candidate-screening result, not certified fact or permission to publish. Existing deeper WordPress publication checks remain necessary.

Validation: `tests/test_shared_discovery.py` tests runtime binding, old history forwarding, fail-closed behavior, and prevents unapproved related terms entering the market pool. Run the existing market-topic tests as regression. Fixtures do not call paid models or publish posts. Production activation and live recommendation quality remain separate acceptance steps.
