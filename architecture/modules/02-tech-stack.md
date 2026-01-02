---
project: wp-auto-blog
created: 2026-01-02
version: 1.0
type: tech-stack
status: approved
---

# Tech Stack - WordPress Auto Blog Pipeline

## 1. Overview

| Category | Technology | Version | License | Cost |
|----------|------------|---------|---------|------|
| **Language** | Python | 3.11+ | PSF | $0 |
| **AI (Primary)** | Google Gemini Flash | 1.5 | Proprietary | $0 (Free Tier) |
| **AI (Fallback)** | OpenAI GPT-4o-mini | - | Proprietary | ~$0.30/mo |
| **Trend Detection** | pytrends, PRAW | 4.9+, 7.7+ | MIT, BSD | $0 |
| **Publishing** | WordPress REST API | v2 | GPL | $0 |
| **Images** | Unsplash, Pexels | - | Free API | $0 |
| **Hosting** | VPS (Optional) | - | - | $0-5/mo |

---

## 2. Core Technologies

### 2.1 Runtime & Language

| Component | Choice | Version | Rationale |
|-----------|--------|---------|-----------|
| **Language** | Python | 3.11+ | Rich ecosystem, AI/ML libraries, type hints |
| **Package Manager** | pip + venv | - | Standard, no extra dependencies |
| **Type Checking** | mypy | 1.8+ | Catch errors early |

**Why Python 3.11+:**
- Performance improvements (10-60% faster than 3.10)
- Better error messages
- tomllib built-in (for TOML configs)
- Exception groups (better async error handling)

---

### 2.2 AI/LLM Providers

#### Primary: Google Gemini Flash

| Aspect | Specification |
|--------|---------------|
| **Model** | gemini-1.5-flash |
| **Free Tier** | 15 RPM, 1M tokens/day |
| **Cost (Paid)** | $0.075/1M input, $0.30/1M output |
| **Context Window** | 1M tokens |
| **Library** | `google-generativeai` |

```python
# Usage Example
import google.generativeai as genai

genai.configure(api_key="YOUR_API_KEY")
model = genai.GenerativeModel('gemini-1.5-flash')

response = model.generate_content(
    "Write a blog post about AI tools...",
    generation_config={
        "temperature": 0.7,
        "max_output_tokens": 3000
    }
)
```

**Why Gemini Flash:**
- Lowest cost per token
- Generous free tier (enough for ~600 articles/day)
- Fast inference speed
- Good quality for blog content

#### Fallback: OpenAI GPT-4o-mini

| Aspect | Specification |
|--------|---------------|
| **Model** | gpt-4o-mini |
| **Cost** | $0.15/1M input, $0.60/1M output |
| **Context Window** | 128K tokens |
| **Library** | `openai` |

```python
# Usage Example
from openai import OpenAI

client = OpenAI(api_key="YOUR_API_KEY")

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You are a tech blogger..."},
        {"role": "user", "content": "Write about AI tools..."}
    ],
    max_tokens=3000,
    temperature=0.7
)
```

**When to Use:**
- Gemini API rate limit hit
- Gemini service unavailable
- Need different writing style

---

### 2.3 Trend Detection

#### Google Trends (pytrends)

| Aspect | Specification |
|--------|---------------|
| **Library** | `pytrends` |
| **API Type** | Unofficial (web scraping) |
| **Rate Limit** | ~10 requests/minute |
| **Cost** | $0 |

```python
from pytrends.request import TrendReq

pytrends = TrendReq(hl='en-US', tz=360)

# Get real-time trending
trending = pytrends.trending_searches(pn='united_states')

# Get related queries
pytrends.build_payload(['AI tools'], timeframe='now 7-d')
related = pytrends.related_queries()
```

**Pros:**
- Free, no auth required
- Real-time trending data
- Regional targeting

**Cons:**
- Unofficial (may break)
- Rate limiting
- No SLA

#### Hacker News API

| Aspect | Specification |
|--------|---------------|
| **API** | Firebase REST API |
| **Auth** | None required |
| **Rate Limit** | Unlimited (be reasonable) |
| **Cost** | $0 |

```python
import requests

# Get top stories
top_ids = requests.get(
    'https://hacker-news.firebaseio.com/v0/topstories.json'
).json()[:30]

# Get story details
story = requests.get(
    f'https://hacker-news.firebaseio.com/v0/item/{top_ids[0]}.json'
).json()
```

**Best For:**
- Tech/developer content
- High-quality sources
- Real-time trends

#### Reddit API (PRAW)

| Aspect | Specification |
|--------|---------------|
| **Library** | `praw` |
| **Auth** | OAuth2 (free app) |
| **Rate Limit** | 60 requests/minute |
| **Cost** | $0 |

```python
import praw

reddit = praw.Reddit(
    client_id="YOUR_ID",
    client_secret="YOUR_SECRET",
    user_agent="auto-blog/1.0"
)

for post in reddit.subreddit("artificial").hot(limit=10):
    print(post.title, post.score)
```

**Recommended Subreddits:**
- r/artificial, r/MachineLearning (AI)
- r/programming, r/technology (Tech)
- r/SaaS, r/startups (Business)

---

### 2.4 Image Providers

#### Unsplash API

| Aspect | Specification |
|--------|---------------|
| **Auth** | API Key (free registration) |
| **Rate Limit** | 50 req/hr (demo), 5000 req/hr (production) |
| **Cost** | $0 |
| **Quality** | High (professional photography) |

```python
import requests

def get_unsplash_image(query: str, api_key: str):
    response = requests.get(
        "https://api.unsplash.com/search/photos",
        headers={"Authorization": f"Client-ID {api_key}"},
        params={"query": query, "per_page": 1, "orientation": "landscape"}
    )
    data = response.json()
    if data["results"]:
        return data["results"][0]["urls"]["regular"]
    return None
```

**Attribution Required:**
- Must credit photographer (we do in alt text)
- Cannot hotlink (must download)

#### Pexels API (Fallback)

| Aspect | Specification |
|--------|---------------|
| **Auth** | API Key |
| **Rate Limit** | 200 req/hr, 20K/month |
| **Cost** | $0 |

```python
import requests

def get_pexels_image(query: str, api_key: str):
    response = requests.get(
        "https://api.pexels.com/v1/search",
        headers={"Authorization": api_key},
        params={"query": query, "per_page": 1}
    )
    data = response.json()
    if data["photos"]:
        return data["photos"][0]["src"]["large"]
    return None
```

---

### 2.5 WordPress Integration

| Aspect | Specification |
|--------|---------------|
| **API** | WordPress REST API v2 |
| **Auth** | Application Password |
| **Library** | `requests` |
| **Cost** | $0 (built-in) |

```python
import requests
import base64

class WordPressClient:
    def __init__(self, site_url, username, app_password):
        self.api_url = f"{site_url}/wp-json/wp/v2"
        credentials = f"{username}:{app_password}"
        token = base64.b64encode(credentials.encode()).decode()
        self.headers = {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json"
        }

    def create_post(self, title, content, status="draft"):
        return requests.post(
            f"{self.api_url}/posts",
            headers=self.headers,
            json={"title": title, "content": content, "status": status}
        ).json()
```

---

## 3. Supporting Libraries

### 3.1 HTTP & Networking

| Library | Purpose | Version |
|---------|---------|---------|
| `requests` | HTTP client | 2.31+ |
| `tenacity` | Retry with backoff | 8.2+ |

### 3.2 Configuration

| Library | Purpose | Version |
|---------|---------|---------|
| `python-dotenv` | .env file loading | 1.0+ |
| `pydantic-settings` | Typed config | 2.1+ |

### 3.3 CLI & UX

| Library | Purpose | Version |
|---------|---------|---------|
| `typer` | CLI framework | 0.9+ |
| `rich` | Beautiful terminal output | 13.7+ |

### 3.4 Content Processing

| Library | Purpose | Version |
|---------|---------|---------|
| `beautifulsoup4` | HTML parsing | 4.12+ |
| `html5lib` | HTML5 parser | 1.1 |

### 3.5 Scheduling

| Library | Purpose | Version |
|---------|---------|---------|
| `schedule` | Python job scheduler | 1.2+ |
| OR: System cron | - | - |

### 3.6 Logging

| Library | Purpose | Version |
|---------|---------|---------|
| `loguru` | Structured logging | 0.7+ |

---

## 4. Development Tools

### 4.1 Code Quality

| Tool | Purpose | Config |
|------|---------|--------|
| `black` | Code formatter | `pyproject.toml` |
| `isort` | Import sorter | `pyproject.toml` |
| `flake8` | Linter | `.flake8` |
| `mypy` | Type checker | `pyproject.toml` |

### 4.2 Testing

| Tool | Purpose | Version |
|------|---------|---------|
| `pytest` | Test framework | 7.4+ |
| `pytest-cov` | Coverage | 4.1+ |
| `responses` | HTTP mocking | 0.24+ |

---

## 5. Requirements Files

### 5.1 requirements.txt (Production)

```
# Core
requests>=2.31.0
python-dotenv>=1.0.0
pydantic>=2.5.0
pydantic-settings>=2.1.0

# CLI
typer[all]>=0.9.0

# Trend Detection
pytrends>=4.9.2
praw>=7.7.1

# AI Providers
openai>=1.12.0
google-generativeai>=0.3.0

# Content Processing
beautifulsoup4>=4.12.0
html5lib>=1.1

# Scheduling
schedule>=1.2.1

# Logging
loguru>=0.7.2

# Utilities
tenacity>=8.2.0
```

### 5.2 requirements-dev.txt (Development)

```
-r requirements.txt

# Testing
pytest>=7.4.0
pytest-cov>=4.1.0
responses>=0.24.0

# Code Quality
black>=23.12.0
isort>=5.13.0
flake8>=6.1.0
mypy>=1.8.0

# Development
ipython>=8.18.0
pre-commit>=3.6.0
```

---

## 6. pyproject.toml

```toml
[project]
name = "wp-auto-blog"
version = "1.0.0"
description = "Automated WordPress blog pipeline with AI content generation"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "you@example.com"}
]

[project.scripts]
wp-auto-blog = "src.main:app"

[tool.black]
line-length = 88
target-version = ['py311']

[tool.isort]
profile = "black"
line_length = 88

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_ignores = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
addopts = "-v --cov=src --cov-report=term-missing"
```

---

## 7. Cost Summary

### 7.1 Monthly Operating Costs

| Component | Min | Typical | Max |
|-----------|-----|---------|-----|
| AI (Gemini Free) | $0 | $0 | $0.50 |
| AI (OpenAI Fallback) | $0 | $0.30 | $1.00 |
| Images (Unsplash/Pexels) | $0 | $0 | $0 |
| Trend APIs | $0 | $0 | $0 |
| VPS (Optional) | $0 | $5 | $10 |
| **Total Tech Stack** | **$0** | **$5.30** | **$11.50** |

### 7.2 Estimated Costs per Article

| Component | Cost/Article |
|-----------|-------------|
| AI Generation | $0.0005 - $0.002 |
| Image Fetching | $0 |
| Publishing | $0 |
| **Total** | **~$0.001** |

---

## 8. Technology Selection Criteria

| Criterion | Weight | Decision Rationale |
|-----------|--------|-------------------|
| **Cost** | 40% | Must be near-zero for MVP |
| **Simplicity** | 25% | 1-person development |
| **Reliability** | 20% | APIs must be stable |
| **Performance** | 10% | Fast enough (< 2min/article) |
| **Scalability** | 5% | Not critical for MVP |

---

## 9. Alternatives Considered

### 9.1 AI Providers

| Alternative | Rejected Because |
|-------------|-----------------|
| Claude API | More expensive than GPT-4o-mini |
| Local LLM (Ollama) | Quality not sufficient for blogs |
| Cohere | Less documentation/support |

### 9.2 Languages

| Alternative | Rejected Because |
|-------------|-----------------|
| Node.js | Less mature AI libraries |
| Go | Overkill for this use case |
| Rust | Steep learning curve |

### 9.3 Databases

| Alternative | Rejected Because |
|-------------|-----------------|
| PostgreSQL | Too heavy for simple caching |
| MongoDB | Unnecessary complexity |
| Redis | Overkill, needs separate service |

---

## 10. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| pytrends breaking | Fallback to HN/Reddit only |
| Gemini rate limit | Fallback to GPT-4o-mini |
| Unsplash limit | Fallback to Pexels |
| API price increase | JSON-based, easy to swap providers |

---

*Document generated by System Designer Agent*
*Date: 2026-01-02*
*Version: 1.0*
