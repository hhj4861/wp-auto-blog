---
project: wp-auto-blog
created: 2026-01-02
version: 1.0
type: infra-design
status: approved
---

# Infrastructure Design - WordPress Auto Blog Pipeline

## 1. Overview

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| **Deployment Model** | Local-first + Optional VPS | Minimize cost, maximize control |
| **Architecture** | Single-node Python | Simple, no orchestration needed |
| **Scheduling** | System Cron / schedule lib | No external dependencies |
| **Monitoring** | Log-based + Email alerts | Sufficient for 1-person operation |

---

## 2. Deployment Options

### 2.1 Option A: Local Machine (Recommended for Start)

```
+--------------------------------------------------+
|                   LOCAL MACHINE                   |
|  (Mac/Linux/Windows with WSL)                    |
+--------------------------------------------------+
|                                                  |
|   +------------------+    +------------------+   |
|   |   Python 3.11    |    |   Cron/Task     |   |
|   |   Virtual Env    |    |   Scheduler     |   |
|   +--------+---------+    +--------+---------+   |
|            |                       |             |
|            +-----------+-----------+             |
|                        |                         |
|            +-----------v-----------+             |
|            |    wp-auto-blog       |             |
|            |    Pipeline           |             |
|            +-----------+-----------+             |
|                        |                         |
+------------------------+-------------------------+
                         |
                         v
              +----------+----------+
              |   External APIs     |
              | (Gemini, WP, etc)   |
              +---------------------+
```

**Setup:**
```bash
# macOS/Linux
crontab -e
# Add:
0 6,12,18 * * * cd ~/wp-auto-blog && ./venv/bin/python -m src.main run >> logs/cron.log 2>&1

# Windows (Task Scheduler)
# Create task: Run at 06:00, 12:00, 18:00
# Action: C:\wp-auto-blog\venv\Scripts\python.exe -m src.main run
```

**Pros:**
- $0 cost
- Full control
- Easy debugging
- No network latency

**Cons:**
- Must keep machine running
- Manual maintenance
- No redundancy

---

### 2.2 Option B: VPS Deployment (Recommended for Production)

```
+--------------------------------------------------+
|                    VPS SERVER                     |
|        (Vultr/DigitalOcean/Hetzner)              |
+--------------------------------------------------+
|                                                  |
|   +------------------+    +------------------+   |
|   |   Ubuntu 22.04   |    |   systemd        |   |
|   |   Python 3.11    |    |   service        |   |
|   +--------+---------+    +--------+---------+   |
|            |                       |             |
|   +--------v---------+    +--------v---------+   |
|   |   wp-auto-blog   |    |   cron daemon    |   |
|   |   /opt/app       |    |                  |   |
|   +--------+---------+    +------------------+   |
|            |                                     |
|   +--------v---------+                           |
|   |   /var/log       |                           |
|   |   logs           |                           |
|   +------------------+                           |
|                                                  |
+--------------------------------------------------+
```

**Recommended Providers:**

| Provider | Tier | Specs | Cost |
|----------|------|-------|------|
| **Vultr** | Cloud Compute | 1 vCPU, 1GB RAM, 25GB | $5/mo |
| **DigitalOcean** | Basic Droplet | 1 vCPU, 1GB RAM, 25GB | $6/mo |
| **Hetzner** | CX11 | 1 vCPU, 2GB RAM, 20GB | $4/mo |
| **Oracle Cloud** | Free Tier | 1 vCPU, 1GB RAM | $0/mo |

**Server Setup Script:**

```bash
#!/bin/bash
# setup-server.sh

set -e

echo "=== Setting up wp-auto-blog server ==="

# Update system
apt update && apt upgrade -y

# Install Python 3.11
apt install -y python3.11 python3.11-venv python3-pip git

# Create app user
useradd -m -s /bin/bash appuser

# Clone repository
cd /opt
git clone https://github.com/your-repo/wp-auto-blog.git
chown -R appuser:appuser wp-auto-blog

# Setup virtual environment
cd wp-auto-blog
sudo -u appuser python3.11 -m venv venv
sudo -u appuser ./venv/bin/pip install -r requirements.txt

# Create log directory
mkdir -p /var/log/wp-auto-blog
chown appuser:appuser /var/log/wp-auto-blog

# Setup .env
cp .env.example .env
echo "Edit /opt/wp-auto-blog/.env with your API keys"

echo "=== Setup complete ==="
```

**Systemd Service:**

```ini
# /etc/systemd/system/wp-auto-blog.service

[Unit]
Description=WordPress Auto Blog Pipeline
After=network.target

[Service]
Type=oneshot
User=appuser
Group=appuser
WorkingDirectory=/opt/wp-auto-blog
ExecStart=/opt/wp-auto-blog/venv/bin/python -m src.main run --topics 3
StandardOutput=append:/var/log/wp-auto-blog/pipeline.log
StandardError=append:/var/log/wp-auto-blog/error.log
Environment=PYTHONPATH=/opt/wp-auto-blog

[Install]
WantedBy=multi-user.target
```

**Systemd Timer:**

```ini
# /etc/systemd/system/wp-auto-blog.timer

[Unit]
Description=Run wp-auto-blog pipeline 3 times daily

[Timer]
OnCalendar=*-*-* 06:00:00
OnCalendar=*-*-* 12:00:00
OnCalendar=*-*-* 18:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

**Enable Service:**

```bash
systemctl daemon-reload
systemctl enable wp-auto-blog.timer
systemctl start wp-auto-blog.timer

# Check status
systemctl list-timers | grep wp-auto-blog
```

---

### 2.3 Option C: Serverless (Future)

```
+--------------------------------------------------+
|              SERVERLESS ARCHITECTURE              |
+--------------------------------------------------+
|                                                  |
|   +------------------+    +------------------+   |
|   |  Cloud Scheduler |    |  Cloud Functions |   |
|   |  (GCP/AWS)       |--->|  (Python 3.11)   |   |
|   +------------------+    +--------+---------+   |
|                                    |             |
|                           +--------v---------+   |
|                           |  Secret Manager  |   |
|                           |  (API Keys)      |   |
|                           +------------------+   |
|                                                  |
+--------------------------------------------------+
```

**Not recommended for MVP:**
- Higher complexity
- Cold start latency
- Harder to debug
- May exceed free tier limits

---

## 3. WordPress Hosting

### 3.1 Recommended Options

| Provider | Type | Cost | Speed | Recommended |
|----------|------|------|-------|-------------|
| **Cloudways** | Managed | $14/mo | Fast | Yes (best balance) |
| **DigitalOcean + RunCloud** | Self-managed | $6+8/mo | Fast | Yes (tech-savvy) |
| **Bluehost** | Shared | $3-10/mo | Slow | No (performance) |
| **SiteGround** | Managed | $15/mo | Fast | Maybe (pricey) |

### 3.2 WordPress Requirements

```yaml
Minimum:
  php: 8.0+
  mysql: 5.7+ or MariaDB 10.3+
  memory: 256MB (512MB recommended)
  ssl: Required (Let's Encrypt free)

Required Plugins:
  - RankMath or Yoast SEO (free)
  - Classic Editor (optional, for API compatibility)

API Configuration:
  - Permalinks: Post name (for clean URLs)
  - Application Password: Enabled (WP 5.6+)
```

### 3.3 WordPress API Setup

```bash
# 1. Enable Application Passwords (usually enabled by default)
# WP Admin > Users > Your Profile > Application Passwords

# 2. Generate new password
# Name: "Auto Blog Pipeline"
# Save the generated password (shown only once)

# 3. Test connection
curl -X GET "https://yourblog.com/wp-json/wp/v2/posts" \
  -H "Authorization: Basic $(echo -n 'username:app_password' | base64)"
```

---

## 4. Security Configuration

### 4.1 Secrets Management

```
+--------------------------------------------------+
|              SECRETS ARCHITECTURE                 |
+--------------------------------------------------+
|                                                  |
|   +------------------+                           |
|   |  .env file       |  (Local development)     |
|   |  chmod 600       |                           |
|   +------------------+                           |
|                                                  |
|   +------------------+                           |
|   |  Environment     |  (VPS production)        |
|   |  Variables       |                           |
|   +------------------+                           |
|                                                  |
+--------------------------------------------------+

NEVER commit:
  - .env
  - API keys
  - WordPress credentials
  - Any secrets
```

### 4.2 .env File Permissions

```bash
# Local/VPS
chmod 600 .env
chown appuser:appuser .env

# Verify
ls -la .env
# -rw------- 1 appuser appuser 512 Jan  2 12:00 .env
```

### 4.3 Firewall Configuration (VPS)

```bash
# UFW (Ubuntu)
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw enable

# Note: No inbound web ports needed
# Pipeline makes outbound requests only
```

### 4.4 SSH Hardening

```bash
# /etc/ssh/sshd_config

PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```

---

## 5. Monitoring & Alerting

### 5.1 Log Management

```
/var/log/wp-auto-blog/
|
+-- pipeline.log          # Main execution log
+-- error.log             # Errors only
+-- pipeline_YYYY-MM-DD.log.gz  # Rotated/compressed
```

**Logrotate Configuration:**

```
# /etc/logrotate.d/wp-auto-blog

/var/log/wp-auto-blog/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 0640 appuser appuser
}
```

### 5.2 Health Check Script

```python
#!/usr/bin/env python3
# scripts/health_check.py

import sys
from datetime import datetime, timedelta
from pathlib import Path

LOG_FILE = Path("/var/log/wp-auto-blog/pipeline.log")
MAX_AGE_HOURS = 12

def check_health():
    if not LOG_FILE.exists():
        print("CRITICAL: Log file not found")
        sys.exit(2)

    # Check last modification time
    mtime = datetime.fromtimestamp(LOG_FILE.stat().st_mtime)
    age = datetime.now() - mtime

    if age > timedelta(hours=MAX_AGE_HOURS):
        print(f"WARNING: No activity for {age.total_seconds() / 3600:.1f} hours")
        sys.exit(1)

    # Check for recent errors
    with open(LOG_FILE) as f:
        lines = f.readlines()[-100:]  # Last 100 lines
        errors = [l for l in lines if "ERROR" in l or "CRITICAL" in l]

    if errors:
        print(f"WARNING: {len(errors)} errors in recent logs")
        print(errors[-1])
        sys.exit(1)

    print("OK: Pipeline healthy")
    sys.exit(0)

if __name__ == "__main__":
    check_health()
```

### 5.3 Email Alerts (Built-in)

```python
# Configured in .env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
NOTIFY_EMAIL=recipient@email.com

# Triggers:
# - Pipeline completion (summary)
# - Any error
# - Quality check failures
```

---

## 6. Backup Strategy

### 6.1 What to Backup

| Data | Location | Frequency | Retention |
|------|----------|-----------|-----------|
| `.env` | /opt/wp-auto-blog | On change | Permanent |
| `data/cache/` | /opt/wp-auto-blog | Daily | 30 days |
| `templates/` | /opt/wp-auto-blog | On change | Git |
| Logs | /var/log/wp-auto-blog | Daily | 7 days |

### 6.2 Backup Script

```bash
#!/bin/bash
# scripts/backup.sh

BACKUP_DIR="/var/backups/wp-auto-blog"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Backup data directory
tar -czf "$BACKUP_DIR/data_$DATE.tar.gz" \
  /opt/wp-auto-blog/data/cache \
  /opt/wp-auto-blog/templates

# Backup .env (encrypted)
gpg --symmetric --cipher-algo AES256 \
  --output "$BACKUP_DIR/env_$DATE.gpg" \
  /opt/wp-auto-blog/.env

# Cleanup old backups (keep 30 days)
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +30 -delete
find "$BACKUP_DIR" -name "*.gpg" -mtime +30 -delete

echo "Backup completed: $DATE"
```

### 6.3 Backup Cron

```bash
# crontab -e
0 2 * * * /opt/wp-auto-blog/scripts/backup.sh >> /var/log/backup.log 2>&1
```

---

## 7. Deployment Pipeline

### 7.1 Manual Deployment (Recommended for MVP)

```bash
#!/bin/bash
# scripts/deploy.sh

set -e

echo "=== Deploying wp-auto-blog ==="

# Pull latest code
cd /opt/wp-auto-blog
git pull origin main

# Update dependencies
./venv/bin/pip install -r requirements.txt

# Run tests
./venv/bin/pytest tests/ -v

# Restart service (if using systemd)
sudo systemctl restart wp-auto-blog.timer

echo "=== Deployment complete ==="
```

### 7.2 GitHub Actions (Optional)

```yaml
# .github/workflows/test.yml

name: Test

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run tests
        run: pytest tests/ -v --cov=src

      - name: Lint
        run: |
          black --check src/
          flake8 src/
          mypy src/
```

---

## 8. Cost Summary

### 8.1 Infrastructure Costs

| Component | Local | VPS (Vultr) | VPS (Oracle Free) |
|-----------|-------|-------------|-------------------|
| Server | $0 | $5/mo | $0 |
| Domain | $1/mo | $1/mo | $1/mo |
| WP Hosting | $14/mo | $14/mo | $14/mo |
| **Total** | **$15/mo** | **$20/mo** | **$15/mo** |

### 8.2 Recommended Setup by Stage

| Stage | Setup | Cost |
|-------|-------|------|
| **MVP (Month 1-2)** | Local + Cloudways WP | $14/mo |
| **Growth (Month 3-6)** | VPS + Cloudways WP | $20/mo |
| **Scale (Month 7+)** | VPS + Cloudways + CDN | $30/mo |

---

## 9. Disaster Recovery

### 9.1 Recovery Procedures

| Scenario | Recovery Steps | RTO |
|----------|---------------|-----|
| VPS failure | Restore from backup to new VPS | 2 hours |
| API key leak | Rotate all keys immediately | 30 min |
| WP site down | Contact hosting support | 1-4 hours |
| Data corruption | Restore from daily backup | 1 hour |

### 9.2 Recovery Script

```bash
#!/bin/bash
# scripts/restore.sh

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: restore.sh <backup_file.tar.gz>"
    exit 1
fi

# Stop service
sudo systemctl stop wp-auto-blog.timer

# Restore data
cd /opt/wp-auto-blog
tar -xzf "$BACKUP_FILE" -C /

# Restart service
sudo systemctl start wp-auto-blog.timer

echo "Restore complete"
```

---

## 10. Checklist

### 10.1 Pre-Deployment

```
[ ] Python 3.11+ installed
[ ] Virtual environment created
[ ] All dependencies installed
[ ] .env configured with API keys
[ ] WordPress API tested
[ ] Cron/Timer configured
[ ] Log rotation configured
[ ] Backup script scheduled
```

### 10.2 Post-Deployment

```
[ ] First pipeline run successful
[ ] Email notifications working
[ ] Logs being written
[ ] No errors in last 24h
```

---

*Document generated by System Designer Agent*
*Date: 2026-01-02*
*Version: 1.0*
