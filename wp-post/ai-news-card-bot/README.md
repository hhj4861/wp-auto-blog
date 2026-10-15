# Daily AI Tech Card News

This isolated wp-post module fetches fresh Claude Code, Codex, MCP and AI open-source releases, produces a Korean daily digest, renders 1080x1350 JPG cards, and sends them as a Telegram photo album.

Schedule: 23:00 UTC daily, approximately 08:00 Korea time the following morning. Scheduled GitHub Actions may be delayed.

Setup GitHub Actions secrets in repository settings:
- TELEGRAM_BOT_TOKEN: Telegram bot API token
- TELEGRAM_CHAT_ID: Telegram destination chat ID
- OPENAI_API_KEY: recommended for Korean summarization; otherwise original English article titles remain

In Actions, choose Daily AI Tech Card News and first launch with dry_run enabled. Inspect the generated image artifact, then launch with dry_run disabled to send a live message.

A failing source is logged and skipped. If no dated articles from the last 72 hours exist, delivery stops instead of inventing news. News excerpts are not substitutes for checking original release notes. Feed timestamps may differ from announcement dates. The code is isolated in wp-post/ai-news-card-bot.
