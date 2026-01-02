---
project: wp-auto-blog
created: 2026-01-02
version: 1.0
type: system-design
status: approved
---

# WordPress Auto Blog Pipeline - System Design

## 1. Executive Summary

| Item | Value |
|------|-------|
| **Architecture Pattern** | Pipeline Architecture (Sequential Processing) |
| **Language** | Python 3.11+ |
| **Primary Interface** | CLI + Cron Scheduler |
| **External Dependencies** | 6 APIs (all free/low-cost) |
| **Estimated Dev Time** | 2-3 weeks (1 developer) |

---

## 2. System Architecture

### 2.1 High-Level Architecture Diagram

```
+============================================================================+
|                         WP-AUTO-BLOG PIPELINE                               |
+============================================================================+
|                                                                             |
|   +---------------------------+                                             |
|   |       SCHEDULER           |   <- Cron / schedule library               |
|   |   (6:00, 12:00, 18:00)    |                                            |
|   +------------+--------------+                                             |
|                |                                                            |
|                v                                                            |
|   +---------------------------+      +---------------------------+          |
|   |    TREND DETECTOR         |----->|      EXTERNAL APIs        |          |
|   |  - Google Trends          |      | - pytrends (unofficial)   |          |
|   |  - Hacker News            |      | - HN Firebase API         |          |
|   |  - Reddit                 |      | - Reddit API (PRAW)       |          |
|   +------------+--------------+      +---------------------------+          |
|                |                                                            |
|                | topics[]                                                   |
|                v                                                            |
|   +---------------------------+      +---------------------------+          |
|   |   CONTENT GENERATOR       |----->|       LLM APIs            |          |
|   |  - Prompt Template        |      | - Gemini Flash (primary)  |          |
|   |  - HTML Formatter         |      | - GPT-4o-mini (fallback)  |          |
|   +------------+--------------+      +---------------------------+          |
|                |                                                            |
|                | content                                                    |
|                v                                                            |
|   +---------------------------+      +---------------------------+          |
|   |    IMAGE FETCHER          |----->|      IMAGE APIs           |          |
|   |  - Keyword Extraction     |      | - Unsplash (primary)      |          |
|   |  - Alt Text Generation    |      | - Pexels (fallback)       |          |
|   +------------+--------------+      +---------------------------+          |
|                |                                                            |
|                | content + images                                           |
|                v                                                            |
|   +---------------------------+                                             |
|   |   QUALITY CHECKER         |                                             |
|   |  - Word Count             |                                             |
|   |  - Keyword Density        |                                             |
|   |  - Structure Validation   |                                             |
|   |  - Duplicate Check        |                                             |
|   +------------+--------------+                                             |
|                |                                                            |
|                | PASS/FAIL                                                  |
|                v                                                            |
|   +---------------------------+      +---------------------------+          |
|   |   WORDPRESS CLIENT        |----->|    WORDPRESS REST API     |          |
|   |  - Media Upload           |      | - /wp-json/wp/v2/posts    |          |
|   |  - Post Creation          |      | - /wp-json/wp/v2/media    |          |
|   |  - Category/Tag Mgmt      |      | - Application Password    |          |
|   +------------+--------------+      +---------------------------+          |
|                |                                                            |
|                | result                                                     |
|                v                                                            |
|   +---------------------------+      +---------------------------+          |
|   |      NOTIFIER             |----->|    NOTIFICATION APIs      |          |
|   |  - Success/Error Alert    |      | - SMTP (Email)            |          |
|   |  - Summary Report         |      | - Slack Webhook (optional)|          |
|   +---------------------------+      +---------------------------+          |
|                                                                             |
|   +---------------------------+                                             |
|   |       SHARED MODULES      |                                             |
|   |  - config.py              |                                             |
|   |  - logger.py              |                                             |
|   |  - cache.py               |                                             |
|   |  - retry.py               |                                             |
|   +---------------------------+                                             |
|                                                                             |
+============================================================================+
```

### 2.2 Component Responsibilities

| Component | Responsibility | Input | Output |
|-----------|---------------|-------|--------|
| **Scheduler** | Trigger pipeline at intervals | Cron schedule | Pipeline execution |
| **TrendDetector** | Discover trending topics | API sources | `List[Topic]` |
| **ContentGenerator** | Generate blog content | Topic | HTML content |
| **ImageFetcher** | Find relevant images | Keywords | `List[Image]` |
| **QualityChecker** | Validate content quality | Content | PASS/FAIL + feedback |
| **WordPressClient** | Publish to WordPress | Content + Images | Post URL |
| **Notifier** | Send alerts | Result | Email/Slack message |

---

## 3. Package Structure

```
wp-auto-blog/
|
+-- src/
|   +-- __init__.py
|   |
|   +-- core/                           # Business Logic (Framework Independent)
|   |   +-- __init__.py
|   |   +-- domain/
|   |   |   +-- __init__.py
|   |   |   +-- entities.py             # Topic, Article, Image dataclasses
|   |   |   +-- enums.py                # ArticleType, QualityStatus
|   |   |   +-- exceptions.py           # Custom exceptions
|   |   |
|   |   +-- use_cases/
|   |   |   +-- __init__.py
|   |   |   +-- detect_trends.py        # Trend detection logic
|   |   |   +-- generate_content.py     # Content generation logic
|   |   |   +-- fetch_images.py         # Image fetching logic
|   |   |   +-- check_quality.py        # Quality validation logic
|   |   |   +-- publish_post.py         # Publishing logic
|   |   |   +-- run_pipeline.py         # Full pipeline orchestration
|   |   |
|   |   +-- ports/
|   |       +-- __init__.py
|   |       +-- trend_source.py         # Abstract trend source interface
|   |       +-- llm_provider.py         # Abstract LLM interface
|   |       +-- image_provider.py       # Abstract image provider interface
|   |       +-- blog_publisher.py       # Abstract publisher interface
|   |       +-- notifier.py             # Abstract notifier interface
|   |       +-- cache_store.py          # Abstract cache interface
|   |
|   +-- adapters/                       # External Integrations
|   |   +-- __init__.py
|   |   +-- trends/
|   |   |   +-- __init__.py
|   |   |   +-- google_trends.py        # pytrends adapter
|   |   |   +-- hacker_news.py          # HN API adapter
|   |   |   +-- reddit.py               # PRAW adapter
|   |   |
|   |   +-- llm/
|   |   |   +-- __init__.py
|   |   |   +-- gemini.py               # Google Gemini adapter
|   |   |   +-- openai_gpt.py           # OpenAI GPT adapter
|   |   |
|   |   +-- images/
|   |   |   +-- __init__.py
|   |   |   +-- unsplash.py             # Unsplash API adapter
|   |   |   +-- pexels.py               # Pexels API adapter
|   |   |
|   |   +-- publishers/
|   |   |   +-- __init__.py
|   |   |   +-- wordpress.py            # WordPress REST API adapter
|   |   |
|   |   +-- notifiers/
|   |   |   +-- __init__.py
|   |   |   +-- email.py                # SMTP email adapter
|   |   |   +-- slack.py                # Slack webhook adapter
|   |   |
|   |   +-- cache/
|   |       +-- __init__.py
|   |       +-- json_cache.py           # JSON file cache adapter
|   |       +-- sqlite_cache.py         # SQLite cache adapter (optional)
|   |
|   +-- shared/                         # Shared Utilities
|   |   +-- __init__.py
|   |   +-- config.py                   # Configuration management
|   |   +-- logger.py                   # Logging setup (loguru)
|   |   +-- retry.py                    # Retry decorator with backoff
|   |   +-- rate_limiter.py             # API rate limiting
|   |   +-- html_utils.py               # HTML processing utilities
|   |   +-- text_utils.py               # Text processing utilities
|   |
|   +-- main.py                         # CLI entry point
|   +-- scheduler.py                    # Scheduler daemon
|
+-- templates/
|   +-- prompts/
|       +-- review.yaml                 # Review article prompt
|       +-- comparison.yaml             # Comparison article prompt
|       +-- guide.yaml                  # How-to guide prompt
|       +-- list.yaml                   # List article prompt
|       +-- news.yaml                   # News analysis prompt
|
+-- data/
|   +-- cache/                          # Keyword cache (JSON/SQLite)
|   |   +-- .gitkeep
|   +-- logs/                           # Log files (7-day retention)
|       +-- .gitkeep
|
+-- tests/
|   +-- __init__.py
|   +-- unit/
|   |   +-- __init__.py
|   |   +-- test_entities.py
|   |   +-- test_detect_trends.py
|   |   +-- test_generate_content.py
|   |   +-- test_check_quality.py
|   +-- integration/
|   |   +-- __init__.py
|   |   +-- test_wordpress_client.py
|   |   +-- test_end_to_end.py
|   +-- conftest.py                     # pytest fixtures
|
+-- .env.example                        # Environment variables template
+-- .gitignore
+-- requirements.txt
+-- requirements-dev.txt
+-- setup.py
+-- pyproject.toml
+-- README.md
```

---

## 4. Data Flow

### 4.1 Pipeline Sequence Diagram

```
Scheduler    TrendDetector    ContentGenerator    ImageFetcher    QualityChecker    WordPressClient    Notifier
    |              |                 |                 |                 |                  |              |
    |--trigger---->|                 |                 |                 |                  |              |
    |              |                 |                 |                 |                  |              |
    |              |--[Google Trends API]              |                 |                  |              |
    |              |--[Hacker News API]                |                 |                  |              |
    |              |--[Reddit API]                     |                 |                  |              |
    |              |                 |                 |                 |                  |              |
    |              |<--topics[]------|                 |                 |                  |              |
    |              |                 |                 |                 |                  |              |
    |     for each topic:            |                 |                 |                  |              |
    |              |                 |                 |                 |                  |              |
    |              |----topic------->|                 |                 |                  |              |
    |              |                 |--[LLM API]----->|                 |                  |              |
    |              |                 |<--content-------|                 |                  |              |
    |              |                 |                 |                 |                  |              |
    |              |                 |----keywords---->|                 |                  |              |
    |              |                 |                 |--[Image API]--->|                  |              |
    |              |                 |                 |<--images[]------|                  |              |
    |              |                 |                 |                 |                  |              |
    |              |                 |----content + images-------------->|                  |              |
    |              |                 |                 |                 |--validate------->|              |
    |              |                 |                 |                 |<--PASS/FAIL------|              |
    |              |                 |                 |                 |                  |              |
    |              |                 |   if PASS:      |                 |                  |              |
    |              |                 |                 |                 |----publish------>|              |
    |              |                 |                 |                 |                  |--[WP API]-->|
    |              |                 |                 |                 |                  |<--post_url--|
    |              |                 |                 |                 |                  |              |
    |              |                 |                 |                 |                  |---result--->|
    |              |                 |                 |                 |                  |              |--[Email]-->
    |              |                 |                 |                 |                  |              |
    |<--complete---|-----------------|-----------------|-----------------|------------------|--------------|
```

### 4.2 Data Entities

```python
# core/domain/entities.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List

class ArticleType(Enum):
    REVIEW = "review"
    COMPARISON = "comparison"
    GUIDE = "guide"
    LIST = "list"
    NEWS = "news"

class QualityStatus(Enum):
    PASS = "pass"
    FAIL = "fail"

@dataclass
class Topic:
    """Trending topic from various sources"""
    title: str
    keywords: List[str]
    source: str  # google_trends, hacker_news, reddit
    score: int  # Relevance score (0-100)
    suggested_title: Optional[str] = None
    article_type: ArticleType = ArticleType.NEWS
    url: Optional[str] = None  # Source URL for reference
    detected_at: datetime = field(default_factory=datetime.now)

@dataclass
class Image:
    """Image metadata for blog post"""
    url: str
    alt_text: str
    source: str  # unsplash, pexels
    photographer: Optional[str] = None
    width: int = 0
    height: int = 0

@dataclass
class Article:
    """Generated blog article"""
    title: str
    content: str  # HTML content
    meta_description: str
    keywords: List[str]
    article_type: ArticleType
    images: List[Image] = field(default_factory=list)
    featured_image: Optional[Image] = None
    word_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class QualityReport:
    """Quality check result"""
    status: QualityStatus
    word_count: int
    keyword_density: float
    heading_count: dict  # {"h2": 5, "h3": 3}
    image_count: int
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

@dataclass
class PublishResult:
    """WordPress publish result"""
    success: bool
    post_id: Optional[int] = None
    post_url: Optional[str] = None
    error: Optional[str] = None
```

---

## 5. Interface Definitions (Ports)

### 5.1 TrendSource Port

```python
# core/ports/trend_source.py

from abc import ABC, abstractmethod
from typing import List
from core.domain.entities import Topic

class TrendSource(ABC):
    """Abstract interface for trend data sources"""

    @abstractmethod
    def fetch_trending(self, limit: int = 10) -> List[Topic]:
        """Fetch trending topics from the source"""
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        """Return the name of this source"""
        pass
```

### 5.2 LLMProvider Port

```python
# core/ports/llm_provider.py

from abc import ABC, abstractmethod
from core.domain.entities import Topic, Article

class LLMProvider(ABC):
    """Abstract interface for LLM providers"""

    @abstractmethod
    def generate_article(self, topic: Topic, prompt_template: str) -> Article:
        """Generate article content from topic"""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the name of this provider"""
        pass
```

### 5.3 ImageProvider Port

```python
# core/ports/image_provider.py

from abc import ABC, abstractmethod
from typing import List
from core.domain.entities import Image

class ImageProvider(ABC):
    """Abstract interface for image providers"""

    @abstractmethod
    def search_images(self, query: str, count: int = 3) -> List[Image]:
        """Search images by query"""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the name of this provider"""
        pass
```

### 5.4 BlogPublisher Port

```python
# core/ports/blog_publisher.py

from abc import ABC, abstractmethod
from core.domain.entities import Article, PublishResult

class BlogPublisher(ABC):
    """Abstract interface for blog publishers"""

    @abstractmethod
    def publish(self, article: Article, status: str = "draft") -> PublishResult:
        """Publish article to blog platform"""
        pass

    @abstractmethod
    def upload_image(self, image_url: str, filename: str) -> int:
        """Upload image and return media ID"""
        pass
```

---

## 6. API Specifications

### 6.1 External API Summary

| API | Purpose | Auth | Rate Limit | Cost |
|-----|---------|------|------------|------|
| **Google Trends** | Trend detection | None | ~10 req/min | $0 |
| **Hacker News** | Tech trends | None | Unlimited | $0 |
| **Reddit** | Community trends | OAuth2 | 60 req/min | $0 |
| **Gemini Flash** | Content generation | API Key | 15 RPM (free) | $0-0.30/mo |
| **GPT-4o-mini** | Content fallback | API Key | Tier-based | $0-0.50/mo |
| **Unsplash** | Images | API Key | 50 req/hr | $0 |
| **Pexels** | Image fallback | API Key | 200 req/hr | $0 |
| **WordPress** | Publishing | App Password | Host-based | $0 |

### 6.2 WordPress REST API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/wp-json/wp/v2/posts` | POST | Create new post |
| `/wp-json/wp/v2/posts/{id}` | PUT | Update post |
| `/wp-json/wp/v2/media` | POST | Upload media |
| `/wp-json/wp/v2/categories` | GET/POST | Manage categories |
| `/wp-json/wp/v2/tags` | GET/POST | Manage tags |

---

## 7. Configuration Management

### 7.1 Environment Variables (.env)

```bash
# .env.example

# WordPress Configuration
WP_SITE_URL=https://yourblog.com
WP_USERNAME=admin
WP_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx

# AI API Keys
GEMINI_API_KEY=your-gemini-api-key
OPENAI_API_KEY=your-openai-api-key

# Image API Keys
UNSPLASH_ACCESS_KEY=your-unsplash-key
PEXELS_API_KEY=your-pexels-key

# Reddit API (optional)
REDDIT_CLIENT_ID=your-client-id
REDDIT_CLIENT_SECRET=your-secret
REDDIT_USER_AGENT=auto-blog/1.0

# Notification
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
NOTIFY_EMAIL=recipient@email.com

# Optional: Slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx

# Pipeline Settings
PIPELINE_TOPICS_PER_RUN=3
PIPELINE_DRY_RUN=false
PIPELINE_DEFAULT_STATUS=draft
LOG_LEVEL=INFO
```

### 7.2 Configuration Class

```python
# shared/config.py

from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application configuration from environment variables"""

    # WordPress
    wp_site_url: str
    wp_username: str
    wp_app_password: str

    # AI Providers
    gemini_api_key: str
    openai_api_key: Optional[str] = None

    # Image Providers
    unsplash_access_key: str
    pexels_api_key: Optional[str] = None

    # Reddit (optional)
    reddit_client_id: Optional[str] = None
    reddit_client_secret: Optional[str] = None
    reddit_user_agent: str = "auto-blog/1.0"

    # Notification
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    notify_email: str
    slack_webhook_url: Optional[str] = None

    # Pipeline
    pipeline_topics_per_run: int = 3
    pipeline_dry_run: bool = False
    pipeline_default_status: str = "draft"
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

---

## 8. Error Handling Strategy

### 8.1 Error Categories

| Category | Example | Handling |
|----------|---------|----------|
| **Transient** | API timeout, rate limit | Retry with backoff (3 attempts) |
| **Recoverable** | Image not found | Skip and continue with fallback |
| **Fatal** | Invalid credentials | Stop and notify |

### 8.2 Retry Decorator

```python
# shared/retry.py

import time
from functools import wraps
from typing import Tuple, Type
from loguru import logger

def retry_with_backoff(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """Retry decorator with exponential backoff"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    wait_time = backoff_factor ** attempt
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
            logger.error(f"All {max_retries} attempts failed")
            raise last_exception
        return wrapper
    return decorator
```

---

## 9. Quality Validation Rules

### 9.1 Validation Criteria

```python
# core/use_cases/check_quality.py

QUALITY_RULES = {
    "word_count": {
        "min": 1500,
        "target": 2000,
        "max": 5000
    },
    "keyword_density": {
        "min": 0.5,  # 0.5%
        "max": 2.5   # 2.5%
    },
    "headings": {
        "h2_min": 4,
        "h3_min": 2
    },
    "images": {
        "min": 3,
        "max": 10
    },
    "meta_description": {
        "min_length": 120,
        "max_length": 160
    },
    "internal_links": {
        "min": 2
    },
    "external_links": {
        "min": 1
    }
}
```

### 9.2 Quality Checker Implementation

```python
from core.domain.entities import Article, QualityReport, QualityStatus
from bs4 import BeautifulSoup

class QualityChecker:
    def check(self, article: Article, target_keywords: List[str]) -> QualityReport:
        issues = []
        suggestions = []

        # Parse HTML
        soup = BeautifulSoup(article.content, 'html.parser')
        text = soup.get_text()

        # Word count
        word_count = len(text.split())
        if word_count < QUALITY_RULES["word_count"]["min"]:
            issues.append(f"Word count too low: {word_count}")

        # Keyword density
        keyword_count = sum(
            text.lower().count(kw.lower())
            for kw in target_keywords
        )
        density = (keyword_count / word_count) * 100 if word_count > 0 else 0

        if density < QUALITY_RULES["keyword_density"]["min"]:
            suggestions.append("Consider adding more keywords")
        elif density > QUALITY_RULES["keyword_density"]["max"]:
            issues.append("Keyword density too high (keyword stuffing)")

        # Heading count
        h2_count = len(soup.find_all('h2'))
        h3_count = len(soup.find_all('h3'))

        if h2_count < QUALITY_RULES["headings"]["h2_min"]:
            issues.append(f"Not enough H2 headings: {h2_count}")

        # Image count
        image_count = len(article.images)
        if image_count < QUALITY_RULES["images"]["min"]:
            issues.append(f"Not enough images: {image_count}")

        # Determine status
        status = QualityStatus.FAIL if issues else QualityStatus.PASS

        return QualityReport(
            status=status,
            word_count=word_count,
            keyword_density=density,
            heading_count={"h2": h2_count, "h3": h3_count},
            image_count=image_count,
            issues=issues,
            suggestions=suggestions
        )
```

---

## 10. Caching Strategy

### 10.1 Cache Design

| Cache Type | Purpose | TTL | Storage |
|------------|---------|-----|---------|
| **Keyword Cache** | Avoid duplicate topics | 30 days | JSON/SQLite |
| **Image Cache** | Reduce API calls | 7 days | JSON |
| **Rate Limit** | Track API usage | 1 hour | Memory |

### 10.2 Duplicate Check

```python
# adapters/cache/json_cache.py

import json
from pathlib import Path
from datetime import datetime, timedelta
from difflib import SequenceMatcher

class KeywordCache:
    def __init__(self, cache_file: Path, ttl_days: int = 30):
        self.cache_file = cache_file
        self.ttl_days = ttl_days
        self._load()

    def _load(self):
        if self.cache_file.exists():
            with open(self.cache_file) as f:
                self.cache = json.load(f)
        else:
            self.cache = {"keywords": []}

    def _save(self):
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2, default=str)

    def is_duplicate(self, title: str, threshold: float = 0.7) -> bool:
        """Check if title is too similar to cached entries"""
        self._cleanup_expired()

        for entry in self.cache["keywords"]:
            similarity = SequenceMatcher(
                None, title.lower(), entry["title"].lower()
            ).ratio()
            if similarity >= threshold:
                return True
        return False

    def add(self, title: str, keywords: List[str]):
        """Add topic to cache"""
        self.cache["keywords"].append({
            "title": title,
            "keywords": keywords,
            "added_at": datetime.now().isoformat()
        })
        self._save()

    def _cleanup_expired(self):
        """Remove entries older than TTL"""
        cutoff = datetime.now() - timedelta(days=self.ttl_days)
        self.cache["keywords"] = [
            entry for entry in self.cache["keywords"]
            if datetime.fromisoformat(entry["added_at"]) > cutoff
        ]
```

---

## 11. Logging Strategy

### 11.1 Log Configuration

```python
# shared/logger.py

from loguru import logger
from pathlib import Path
import sys

def setup_logger(log_dir: Path, log_level: str = "INFO"):
    """Configure loguru logger"""

    # Remove default handler
    logger.remove()

    # Console output
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan> | "
               "<level>{message}</level>"
    )

    # File output (rotation: 10MB, retention: 7 days)
    logger.add(
        log_dir / "pipeline_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"
    )

    return logger
```

---

## 12. CLI Interface

### 12.1 Command Structure

```bash
# Run full pipeline
python -m src.main run --topics 3 --status draft

# Detect trends only
python -m src.main trends --source all --limit 10

# Generate single article
python -m src.main generate --topic "AI Tools 2025" --type review

# Check quality of existing content
python -m src.main check --file article.html

# Test WordPress connection
python -m src.main test-wp

# Start scheduler daemon
python -m src.scheduler start --schedule "0 6,12,18 * * *"
```

### 12.2 CLI Implementation

```python
# main.py

import typer
from typing import Optional
from enum import Enum

app = typer.Typer(help="WordPress Auto Blog Pipeline")

class ArticleTypeArg(str, Enum):
    review = "review"
    comparison = "comparison"
    guide = "guide"
    list = "list"
    news = "news"

@app.command()
def run(
    topics: int = typer.Option(3, "--topics", "-t", help="Number of topics to process"),
    status: str = typer.Option("draft", "--status", "-s", help="Post status: draft/publish"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Don't publish, just simulate")
):
    """Run the full pipeline"""
    from core.use_cases.run_pipeline import PipelineRunner
    runner = PipelineRunner()
    runner.execute(topics=topics, status=status, dry_run=dry_run)

@app.command()
def trends(
    source: str = typer.Option("all", "--source", help="Source: google/hn/reddit/all"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of trends to fetch")
):
    """Detect trending topics"""
    from core.use_cases.detect_trends import TrendDetector
    detector = TrendDetector()
    topics = detector.detect(source=source, limit=limit)
    for t in topics:
        typer.echo(f"[{t.score}] {t.title} ({t.source})")

@app.command(name="test-wp")
def test_wordpress():
    """Test WordPress connection"""
    from adapters.publishers.wordpress import WordPressAdapter
    wp = WordPressAdapter()
    if wp.test_connection():
        typer.echo("WordPress connection successful!")
    else:
        typer.echo("WordPress connection failed!", err=True)
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
```

---

## 13. Dependencies

### 13.1 requirements.txt

```
# Core
requests>=2.31.0
python-dotenv>=1.0.0
pydantic>=2.5.0
pydantic-settings>=2.1.0

# CLI
typer>=0.9.0
rich>=13.7.0

# Trend Detection
pytrends>=4.9.2
praw>=7.7.1

# AI
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
tenacity>=8.2.0  # Advanced retry
```

### 13.2 requirements-dev.txt

```
# Testing
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-asyncio>=0.21.0
responses>=0.24.0  # Mock HTTP

# Code Quality
black>=23.12.0
isort>=5.13.0
flake8>=6.1.0
mypy>=1.8.0

# Development
ipython>=8.18.0
```

---

## 14. Deployment

### 14.1 Local Development

```bash
# 1. Clone repository
git clone https://github.com/your-repo/wp-auto-blog.git
cd wp-auto-blog

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 5. Run tests
pytest

# 6. Run pipeline
python -m src.main run --topics 1 --dry-run
```

### 14.2 Production (VPS)

```bash
# Using systemd service
# /etc/systemd/system/wp-auto-blog.service

[Unit]
Description=WordPress Auto Blog Pipeline
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=/opt/wp-auto-blog
ExecStart=/opt/wp-auto-blog/venv/bin/python -m src.scheduler start
Restart=always
RestartSec=10
Environment=PYTHONPATH=/opt/wp-auto-blog

[Install]
WantedBy=multi-user.target
```

### 14.3 Cron Alternative

```bash
# crontab -e
# Run at 6:00, 12:00, 18:00 daily
0 6,12,18 * * * cd /opt/wp-auto-blog && /opt/wp-auto-blog/venv/bin/python -m src.main run --topics 3 >> /var/log/wp-auto-blog.log 2>&1
```

---

## 15. Next Steps

| Priority | Task | Assigned To |
|----------|------|-------------|
| P0 | Create data-model.md (entities, cache schema) | data-architect |
| P0 | Implement core modules | development |
| P1 | Set up CI/CD pipeline | devops |
| P1 | Create prompt templates | development |
| P2 | Add monitoring/alerting | devops |

---

*Document generated by System Designer Agent*
*Date: 2026-01-02*
*Version: 1.0*
