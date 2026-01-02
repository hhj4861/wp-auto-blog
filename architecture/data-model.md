---
project: wp-auto-blog
created: 2026-01-02
version: 1.0
type: data-model
status: approved
---

# WordPress Auto Blog Pipeline - Data Model

## 1. Overview

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| **Primary Storage** | JSON Files | Simple, no DB dependency, git-friendly |
| **Cache Storage** | SQLite (optional) | Faster queries when scaling |
| **Log Storage** | File-based (loguru) | 7-day rotation, compressed |
| **State Management** | JSON Files | Track pipeline execution state |

---

## 2. Entity Relationship Diagram

```
+------------------+       +------------------+       +------------------+
|      Topic       |       |     Article      |       |      Image       |
+------------------+       +------------------+       +------------------+
| id: str (uuid)   |       | id: str (uuid)   |       | id: str (uuid)   |
| title: str       |  1:1  | title: str       |  1:N  | url: str         |
| keywords: list   |------>| content: str     |<------| alt_text: str    |
| source: str      |       | meta_desc: str   |       | source: str      |
| score: int       |       | keywords: list   |       | photographer: str|
| article_type: str|       | article_type: str|       | width: int       |
| url: str         |       | word_count: int  |       | height: int      |
| detected_at: dt  |       | created_at: dt   |       | is_featured: bool|
+------------------+       | topic_id: str    |       | article_id: str  |
                           | status: str      |       +------------------+
                           +------------------+
                                   |
                                   | 1:1
                                   v
                           +------------------+
                           |  QualityReport   |
                           +------------------+
                           | id: str (uuid)   |
                           | article_id: str  |
                           | status: str      |
                           | word_count: int  |
                           | keyword_density: |
                           | heading_count: {}|
                           | image_count: int |
                           | issues: list     |
                           | suggestions: list|
                           | checked_at: dt   |
                           +------------------+

                           +------------------+
                           |  PublishResult   |
                           +------------------+
                           | id: str (uuid)   |
                           | article_id: str  |
                           | success: bool    |
                           | post_id: int     |
                           | post_url: str    |
                           | wp_status: str   |
                           | published_at: dt |
                           | error: str       |
                           +------------------+

+------------------+       +------------------+
|   CacheEntry     |       |   PipelineRun    |
+------------------+       +------------------+
| title: str       |       | id: str (uuid)   |
| keywords: list   |       | started_at: dt   |
| added_at: dt     |       | completed_at: dt |
| expires_at: dt   |       | status: str      |
| source: str      |       | topics_detected: |
+------------------+       | articles_created:|
                           | articles_published|
                           | errors: list     |
                           +------------------+
```

---

## 3. Data Structures (Python Dataclasses)

### 3.1 Core Entities

```python
# src/core/domain/entities.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List
import uuid

# ============================================================
# Enums
# ============================================================

class ArticleType(Enum):
    """Types of blog articles"""
    REVIEW = "review"
    COMPARISON = "comparison"
    GUIDE = "guide"
    LIST = "list"
    NEWS = "news"

class QualityStatus(Enum):
    """Quality check result status"""
    PASS = "pass"
    FAIL = "fail"
    SKIPPED = "skipped"

class TrendSource(Enum):
    """Sources for trending topics"""
    GOOGLE_TRENDS = "google_trends"
    HACKER_NEWS = "hacker_news"
    REDDIT = "reddit"

class PostStatus(Enum):
    """WordPress post status"""
    DRAFT = "draft"
    PENDING = "pending"
    PUBLISH = "publish"
    SCHEDULED = "scheduled"

class PipelineStatus(Enum):
    """Pipeline execution status"""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # Some articles failed

# ============================================================
# Core Entities
# ============================================================

@dataclass
class Topic:
    """
    Trending topic discovered from various sources.
    Represents a potential blog post topic.
    """
    title: str
    keywords: List[str]
    source: TrendSource
    score: int  # Relevance score (0-100)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    suggested_title: Optional[str] = None
    article_type: ArticleType = ArticleType.NEWS
    source_url: Optional[str] = None  # Original source URL
    detected_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "keywords": self.keywords,
            "source": self.source.value,
            "score": self.score,
            "suggested_title": self.suggested_title,
            "article_type": self.article_type.value,
            "source_url": self.source_url,
            "detected_at": self.detected_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Topic":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            title=data["title"],
            keywords=data["keywords"],
            source=TrendSource(data["source"]),
            score=data["score"],
            suggested_title=data.get("suggested_title"),
            article_type=ArticleType(data.get("article_type", "news")),
            source_url=data.get("source_url"),
            detected_at=datetime.fromisoformat(data["detected_at"])
        )


@dataclass
class Image:
    """
    Image metadata for blog post.
    Images are not stored locally - only URLs are referenced.
    """
    url: str
    alt_text: str
    source: str  # "unsplash" or "pexels"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    photographer: Optional[str] = None
    photographer_url: Optional[str] = None
    width: int = 0
    height: int = 0
    is_featured: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "alt_text": self.alt_text,
            "source": self.source,
            "photographer": self.photographer,
            "photographer_url": self.photographer_url,
            "width": self.width,
            "height": self.height,
            "is_featured": self.is_featured
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Image":
        return cls(**data)


@dataclass
class Article:
    """
    Generated blog article with all content and metadata.
    """
    title: str
    content: str  # HTML content
    meta_description: str
    keywords: List[str]
    article_type: ArticleType
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic_id: Optional[str] = None
    images: List[Image] = field(default_factory=list)
    featured_image: Optional[Image] = None
    word_count: int = 0
    category: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    status: PostStatus = PostStatus.DRAFT

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "topic_id": self.topic_id,
            "title": self.title,
            "content": self.content,
            "meta_description": self.meta_description,
            "keywords": self.keywords,
            "article_type": self.article_type.value,
            "images": [img.to_dict() for img in self.images],
            "featured_image": self.featured_image.to_dict() if self.featured_image else None,
            "word_count": self.word_count,
            "category": self.category,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "status": self.status.value
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Article":
        images = [Image.from_dict(img) for img in data.get("images", [])]
        featured = Image.from_dict(data["featured_image"]) if data.get("featured_image") else None
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            topic_id=data.get("topic_id"),
            title=data["title"],
            content=data["content"],
            meta_description=data["meta_description"],
            keywords=data["keywords"],
            article_type=ArticleType(data["article_type"]),
            images=images,
            featured_image=featured,
            word_count=data.get("word_count", 0),
            category=data.get("category"),
            tags=data.get("tags", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            status=PostStatus(data.get("status", "draft"))
        )


@dataclass
class QualityReport:
    """
    Quality check result for an article.
    """
    status: QualityStatus
    word_count: int
    keyword_density: float  # Percentage (0-100)
    heading_count: dict  # {"h2": 5, "h3": 3}
    image_count: int
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    article_id: Optional[str] = None
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    checked_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "article_id": self.article_id,
            "status": self.status.value,
            "word_count": self.word_count,
            "keyword_density": self.keyword_density,
            "heading_count": self.heading_count,
            "image_count": self.image_count,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "checked_at": self.checked_at.isoformat()
        }


@dataclass
class PublishResult:
    """
    Result of publishing an article to WordPress.
    """
    success: bool
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    article_id: Optional[str] = None
    post_id: Optional[int] = None
    post_url: Optional[str] = None
    wp_status: PostStatus = PostStatus.DRAFT
    published_at: Optional[datetime] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "article_id": self.article_id,
            "success": self.success,
            "post_id": self.post_id,
            "post_url": self.post_url,
            "wp_status": self.wp_status.value,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "error": self.error
        }


@dataclass
class PipelineRun:
    """
    Record of a single pipeline execution.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    status: PipelineStatus = PipelineStatus.RUNNING
    topics_detected: int = 0
    articles_created: int = 0
    articles_published: int = 0
    errors: List[str] = field(default_factory=list)
    topic_ids: List[str] = field(default_factory=list)
    article_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status.value,
            "topics_detected": self.topics_detected,
            "articles_created": self.articles_created,
            "articles_published": self.articles_published,
            "errors": self.errors,
            "topic_ids": self.topic_ids,
            "article_ids": self.article_ids
        }
```

---

## 4. File-Based Storage Schema

### 4.1 Directory Structure

```
data/
|
+-- cache/
|   +-- keywords.json           # Keyword/topic duplicate cache
|   +-- images.json             # Image URL cache
|
+-- runs/
|   +-- 2026-01-02_06-00-00.json    # Pipeline run history
|   +-- 2026-01-02_12-00-00.json
|
+-- articles/
|   +-- 2026-01/
|       +-- article_abc123.json     # Generated articles (backup)
|
+-- logs/
    +-- pipeline_2026-01-02.log     # Daily log files
    +-- pipeline_2026-01-02.log.gz  # Compressed old logs
```

### 4.2 Cache Schema (keywords.json)

```json
{
  "version": "1.0",
  "updated_at": "2026-01-02T12:00:00",
  "entries": [
    {
      "title": "Claude 3.5 Sonnet Review",
      "keywords": ["claude", "anthropic", "ai", "llm"],
      "source": "hacker_news",
      "added_at": "2026-01-02T06:00:00",
      "expires_at": "2026-02-01T06:00:00"
    },
    {
      "title": "Best AI Coding Tools 2026",
      "keywords": ["ai", "coding", "tools", "programming"],
      "source": "google_trends",
      "added_at": "2026-01-01T18:00:00",
      "expires_at": "2026-01-31T18:00:00"
    }
  ]
}
```

### 4.3 Pipeline Run Schema

```json
{
  "id": "run_abc123",
  "started_at": "2026-01-02T06:00:00",
  "completed_at": "2026-01-02T06:15:32",
  "status": "completed",
  "config": {
    "topics_per_run": 3,
    "default_status": "draft",
    "sources": ["google_trends", "hacker_news", "reddit"]
  },
  "summary": {
    "topics_detected": 15,
    "topics_filtered": 12,
    "topics_processed": 3,
    "articles_created": 3,
    "articles_passed_quality": 3,
    "articles_published": 3
  },
  "topics": [
    {
      "id": "topic_001",
      "title": "OpenAI GPT-5 Rumors",
      "source": "hacker_news",
      "score": 92,
      "result": "published"
    }
  ],
  "articles": [
    {
      "id": "article_001",
      "topic_id": "topic_001",
      "title": "GPT-5: Everything We Know So Far",
      "word_count": 2150,
      "quality_status": "pass",
      "publish_status": "draft",
      "post_url": "https://yourblog.com/?p=123"
    }
  ],
  "errors": []
}
```

### 4.4 Article Backup Schema

```json
{
  "id": "article_abc123",
  "topic_id": "topic_xyz789",
  "title": "Best AI Tools for Developers in 2026",
  "meta_description": "Discover the top 10 AI tools that every developer should know in 2026. From code assistants to debugging helpers.",
  "keywords": ["ai tools", "developer tools", "coding ai", "programming assistant"],
  "article_type": "list",
  "content": "<h1>Best AI Tools for Developers in 2026</h1><p>...</p>",
  "word_count": 2350,
  "images": [
    {
      "id": "img_001",
      "url": "https://images.unsplash.com/photo-xxx",
      "alt_text": "Developer using AI coding assistant",
      "source": "unsplash",
      "is_featured": true
    }
  ],
  "category": "AI Tools",
  "tags": ["ai", "developer", "tools", "2026"],
  "quality_report": {
    "status": "pass",
    "word_count": 2350,
    "keyword_density": 1.8,
    "heading_count": {"h2": 6, "h3": 4},
    "image_count": 5,
    "issues": [],
    "suggestions": []
  },
  "publish_result": {
    "success": true,
    "post_id": 123,
    "post_url": "https://yourblog.com/best-ai-tools-developers-2026/",
    "wp_status": "draft",
    "published_at": "2026-01-02T06:12:45"
  },
  "created_at": "2026-01-02T06:10:00"
}
```

---

## 5. SQLite Schema (Optional - For Scaling)

When JSON files become slow (>1000 entries), migrate to SQLite:

```sql
-- data/cache/wp_auto_blog.db

-- Keyword Cache Table
CREATE TABLE keyword_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    keywords TEXT NOT NULL,  -- JSON array
    source TEXT NOT NULL,
    title_hash TEXT NOT NULL UNIQUE,  -- For fast duplicate check
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    UNIQUE(title_hash)
);

CREATE INDEX idx_cache_expires ON keyword_cache(expires_at);
CREATE INDEX idx_cache_title_hash ON keyword_cache(title_hash);

-- Pipeline Runs Table
CREATE TABLE pipeline_runs (
    id TEXT PRIMARY KEY,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status TEXT NOT NULL,
    config TEXT NOT NULL,  -- JSON
    summary TEXT NOT NULL,  -- JSON
    errors TEXT,  -- JSON array
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_runs_started ON pipeline_runs(started_at DESC);

-- Articles Table (for analytics)
CREATE TABLE articles (
    id TEXT PRIMARY KEY,
    topic_id TEXT,
    run_id TEXT,
    title TEXT NOT NULL,
    word_count INTEGER,
    quality_status TEXT,
    post_id INTEGER,
    post_url TEXT,
    wp_status TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES pipeline_runs(id)
);

CREATE INDEX idx_articles_created ON articles(created_at DESC);
CREATE INDEX idx_articles_post_id ON articles(post_id);

-- Image Cache Table
CREATE TABLE image_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    query_hash TEXT NOT NULL,
    images TEXT NOT NULL,  -- JSON array
    source TEXT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    UNIQUE(query_hash, source)
);

CREATE INDEX idx_image_cache_query ON image_cache(query_hash);
```

---

## 6. Prompt Template Schema

### 6.1 Template Structure (YAML)

```yaml
# templates/prompts/review.yaml

name: review
description: "Product/Tool review article"
version: "1.0"

system_prompt: |
  You are a professional tech blogger writing for an audience of
  developers and tech enthusiasts. Your writing style is:
  - Clear and concise
  - Technically accurate
  - Engaging and practical
  - SEO-optimized

user_prompt: |
  Write a comprehensive review article about: {{topic}}

  Target keywords: {{keywords}}

  Requirements:
  - Title: Include the main keyword, make it compelling
  - Length: 1,800-2,200 words
  - Structure:
    - Introduction (hook + what you'll learn)
    - Overview/Background
    - Key Features (3-5 with H2 headings)
    - Pros and Cons (table format)
    - Pricing (if applicable)
    - Alternatives comparison (brief)
    - Final Verdict
    - FAQ section (3-5 questions)
  - Include specific examples and use cases
  - Write a meta description (150-160 characters)

  Output format: HTML (use semantic tags: h2, h3, p, ul, li, table)

output_format:
  title: string
  content: html
  meta_description: string
  suggested_tags: list

variables:
  - topic
  - keywords

settings:
  temperature: 0.7
  max_tokens: 3000
```

### 6.2 Template Variables

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `{{topic}}` | string | Main topic/title | "Claude 3.5 Sonnet" |
| `{{keywords}}` | list | Target keywords | ["claude", "ai", "llm"] |
| `{{article_type}}` | enum | Type of article | "review" |
| `{{word_count}}` | int | Target word count | 2000 |
| `{{tone}}` | string | Writing tone | "professional" |
| `{{audience}}` | string | Target audience | "developers" |

---

## 7. Configuration Schema

### 7.1 Quality Rules (YAML)

```yaml
# config/quality_rules.yaml

version: "1.0"

rules:
  word_count:
    min: 1500
    target: 2000
    max: 5000
    weight: 0.3

  keyword_density:
    min: 0.5  # percentage
    max: 2.5
    weight: 0.2

  headings:
    h2:
      min: 4
      max: 10
    h3:
      min: 2
      max: 15
    weight: 0.15

  images:
    min: 3
    max: 10
    weight: 0.15

  meta_description:
    min_length: 120
    max_length: 160
    weight: 0.1

  links:
    internal:
      min: 2
    external:
      min: 1
    weight: 0.1

thresholds:
  pass: 0.7  # 70% of weighted score
  fail: 0.5  # Below 50% is hard fail
```

### 7.2 Source Configuration (YAML)

```yaml
# config/sources.yaml

version: "1.0"

trend_sources:
  google_trends:
    enabled: true
    priority: 1
    geo: "US"
    language: "en-US"
    max_results: 20
    rate_limit:
      requests_per_minute: 10
      delay_between_requests: 6  # seconds

  hacker_news:
    enabled: true
    priority: 2
    endpoints:
      top_stories: "https://hacker-news.firebaseio.com/v0/topstories.json"
      item: "https://hacker-news.firebaseio.com/v0/item/{id}.json"
    max_results: 30
    min_score: 50

  reddit:
    enabled: true
    priority: 3
    subreddits:
      - artificial
      - MachineLearning
      - programming
      - technology
    sort_by: "hot"
    time_filter: "day"
    max_results: 20
    min_score: 100

image_sources:
  unsplash:
    enabled: true
    priority: 1
    orientation: "landscape"
    per_page: 5

  pexels:
    enabled: true
    priority: 2  # fallback
    orientation: "landscape"
    per_page: 5

llm_providers:
  gemini:
    enabled: true
    priority: 1
    model: "gemini-1.5-flash"
    max_tokens: 3000
    temperature: 0.7

  openai:
    enabled: true
    priority: 2  # fallback
    model: "gpt-4o-mini"
    max_tokens: 3000
    temperature: 0.7
```

---

## 8. Validation Rules

### 8.1 Entity Validation

```python
# src/core/domain/validators.py

from pydantic import BaseModel, Field, validator
from typing import List, Optional
from enum import Enum

class TopicValidator(BaseModel):
    """Validation rules for Topic entity"""
    title: str = Field(..., min_length=10, max_length=200)
    keywords: List[str] = Field(..., min_items=1, max_items=10)
    score: int = Field(..., ge=0, le=100)

    @validator('keywords')
    def keywords_not_empty(cls, v):
        if not all(k.strip() for k in v):
            raise ValueError('Keywords cannot be empty strings')
        return [k.strip().lower() for k in v]


class ArticleValidator(BaseModel):
    """Validation rules for Article entity"""
    title: str = Field(..., min_length=20, max_length=100)
    content: str = Field(..., min_length=3000)  # ~500 words minimum
    meta_description: str = Field(..., min_length=50, max_length=160)
    keywords: List[str] = Field(..., min_items=1)

    @validator('content')
    def content_is_html(cls, v):
        if '<' not in v or '>' not in v:
            raise ValueError('Content must be HTML')
        return v

    @validator('meta_description')
    def meta_no_special_chars(cls, v):
        forbidden = ['<', '>', '"', '\n']
        for char in forbidden:
            if char in v:
                raise ValueError(f'Meta description cannot contain {char}')
        return v
```

---

## 9. Migration Strategy

### 9.1 JSON to SQLite Migration

```python
# scripts/migrate_to_sqlite.py

import json
import sqlite3
from pathlib import Path
from datetime import datetime

def migrate_cache(json_file: Path, db_file: Path):
    """Migrate keyword cache from JSON to SQLite"""

    # Load JSON data
    with open(json_file) as f:
        data = json.load(f)

    # Connect to SQLite
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Create table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS keyword_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            keywords TEXT NOT NULL,
            source TEXT NOT NULL,
            title_hash TEXT NOT NULL UNIQUE,
            added_at TIMESTAMP,
            expires_at TIMESTAMP
        )
    ''')

    # Migrate entries
    for entry in data.get('entries', []):
        title_hash = hash(entry['title'].lower())
        cursor.execute('''
            INSERT OR IGNORE INTO keyword_cache
            (title, keywords, source, title_hash, added_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            entry['title'],
            json.dumps(entry['keywords']),
            entry['source'],
            str(title_hash),
            entry['added_at'],
            entry['expires_at']
        ))

    conn.commit()
    conn.close()

    print(f"Migrated {len(data.get('entries', []))} entries to SQLite")
```

---

## 10. Backup Strategy

### 10.1 Automated Backups

```yaml
# Backup Configuration

backup:
  enabled: true
  frequency: daily
  retention: 30  # days
  location: data/backups/

  include:
    - data/cache/keywords.json
    - data/runs/
    - config/

  exclude:
    - data/logs/
    - "*.log"
    - "*.pyc"
```

### 10.2 Backup Script

```python
# scripts/backup.py

import shutil
from datetime import datetime
from pathlib import Path

def create_backup(data_dir: Path, backup_dir: Path):
    """Create timestamped backup of data directory"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"backup_{timestamp}"

    # Create backup
    shutil.copytree(
        data_dir,
        backup_path,
        ignore=shutil.ignore_patterns('*.log', '*.pyc', '__pycache__')
    )

    # Compress
    shutil.make_archive(str(backup_path), 'zip', backup_path)
    shutil.rmtree(backup_path)

    print(f"Backup created: {backup_path}.zip")

    # Cleanup old backups (keep last 30)
    cleanup_old_backups(backup_dir, keep=30)
```

---

## 11. Summary

| Aspect | Decision |
|--------|----------|
| **Primary Storage** | JSON files (simple, portable) |
| **Scaling Option** | SQLite (when >1000 entries) |
| **Cache TTL** | 30 days for keywords, 7 days for images |
| **Log Retention** | 7 days, compressed |
| **Backup Frequency** | Daily, 30-day retention |

---

*Document generated by Data Architect Agent*
*Date: 2026-01-02*
*Version: 1.0*
