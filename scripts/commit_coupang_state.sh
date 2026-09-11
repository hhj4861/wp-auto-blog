#!/usr/bin/env bash
# Must succeed before notification/publication or a subsequent Telegram poll.
set -euo pipefail
test "${GITHUB_REF:-}" = refs/heads/main
git config --local user.email 'github-actions[bot]@users.noreply.github.com'
git config --local user.name 'github-actions[bot]'
for file in data/coupang_requests.json data/topic_queue_general.json data/post_registry_general.json data/posted_market_keywords.json data/category_market_topics.json; do
  if [ -f "$file" ]; then git add "$file"; fi
done
if ! git diff --staged --quiet; then
  git commit -m 'chore: persist Coupang approval state [skip ci]'
fi
# Push even if nothing newly staged: a previous push may have failed.
for attempt in 1 2 3; do
  if git push origin HEAD:main; then exit 0; fi
  # Shared concurrency serializes state writers; only unrelated commits may rebase.
  if ! git pull --rebase origin main; then
    git rebase --abort || true
    exit 1
  fi
done
echo 'State persistence failed; remote effects stopped'
exit 1
