---
project: wp-auto-blog
created: 2026-01-02
version: 1.0
type: mvp-spec
status: approved
---

# MVP Specification - WordPress Auto Blog Pipeline

## 1. MVP Scope

### 1.1 In Scope (Must Have)

| Feature | Description | Priority |
|---------|-------------|----------|
| **Trend Detection** | Google Trends + Hacker News | P0 |
| **Content Generation** | Gemini Flash (primary), GPT-4o-mini (fallback) | P0 |
| **Image Fetching** | Unsplash API | P0 |
| **Quality Check** | Word count, keyword density, structure | P0 |
| **WordPress Publishing** | REST API, draft status | P0 |
| **CLI Interface** | Run pipeline, check status | P0 |

### 1.2 Out of Scope (Future)

| Feature | Reason | Target Phase |
|---------|--------|--------------|
| Web Dashboard | Not needed for 1-person use | Phase 3 |
| Multi-blog Support | Single blog sufficient for MVP | Phase 3 |
| GA4 Integration | Focus on content first | Phase 3 |
| Auto-Update Old Posts | Nice-to-have | Phase 4 |
| A/B Testing | Optimization phase | Phase 4 |
| Reddit API | Lower priority source | Phase 2 |
| Slack Notifications | Email sufficient | Phase 2 |

---

## 2. Core User Flows

### 2.1 Primary Flow: Scheduled Pipeline Run

```
[Cron Trigger]
    |
    v
[1. Detect Trends]
    |-- Google Trends API
    |-- Hacker News API
    |
    v
[2. Filter & Score]
    |-- Relevance scoring (0-100)
    |-- Duplicate check (cache)
    |-- Select top N topics
    |
    v
[3. For Each Topic:]
    |
    |-- [3a. Generate Content]
    |       |-- Load prompt template
    |       |-- Call Gemini Flash
    |       |-- Fallback to GPT-4o-mini
    |       |-- Parse HTML output
    |
    |-- [3b. Fetch Images]
    |       |-- Extract keywords
    |       |-- Search Unsplash
    |       |-- Get 3-5 images
    |
    |-- [3c. Quality Check]
    |       |-- Word count >= 1500
    |       |-- Keyword density 0.5-2.5%
    |       |-- H2 count >= 4
    |       |-- Image count >= 3
    |       |
    |       v
    |   [PASS?]--No--> [Log & Skip]
    |       |
    |      Yes
    |       |
    |-- [3d. Publish to WordPress]
    |       |-- Upload featured image
    |       |-- Create draft post
    |       |-- Set categories/tags
    |
    v
[4. Send Summary Email]
    |-- Articles created: N
    |-- Articles published: M
    |-- Errors: K
    |
    v
[Done]
```

### 2.2 Secondary Flow: Manual Run

```bash
# Run full pipeline
python -m src.main run --topics 3

# Dry run (no publishing)
python -m src.main run --topics 1 --dry-run

# Generate single article
python -m src.main generate --topic "AI Tools 2025" --type review
```

---

## 3. Module Specifications

### 3.1 TrendDetector Module

**Purpose:** Discover trending topics from multiple sources

**Inputs:**
- Source selection (google, hn, all)
- Limit (default: 10 per source)
- Niche filter keywords (optional)

**Outputs:**
```python
@dataclass
class Topic:
    title: str
    keywords: List[str]
    source: str
    score: int  # 0-100
    suggested_title: Optional[str]
    article_type: ArticleType
```

**Logic:**
1. Fetch trends from enabled sources
2. Filter by niche relevance (if configured)
3. Score by: freshness, engagement, keyword match
4. Check duplicate cache (70% similarity threshold)
5. Return top N unique topics

**Error Handling:**
- API timeout: Retry 3x with backoff
- Rate limit: Skip source, use others
- Empty results: Log warning, continue

---

### 3.2 ContentGenerator Module

**Purpose:** Generate blog articles using AI

**Inputs:**
```python
@dataclass
class GenerateRequest:
    topic: Topic
    article_type: ArticleType
    word_count_target: int = 2000
    tone: str = "professional"
```

**Outputs:**
```python
@dataclass
class Article:
    title: str
    content: str  # HTML
    meta_description: str
    keywords: List[str]
    word_count: int
```

**Prompt Template Structure:**
```yaml
# templates/prompts/review.yaml
name: review
system_prompt: |
  You are a tech blogger...

user_prompt: |
  Write a review about: {{topic}}
  Keywords: {{keywords}}
  Requirements:
    - 1800-2200 words
    - H2/H3 structure
    - Include FAQ section
    - Output as HTML
```

**Provider Priority:**
1. Gemini Flash (default)
2. GPT-4o-mini (fallback)

**Error Handling:**
- API error: Fallback to secondary provider
- Invalid output: Retry with modified prompt
- Rate limit: Wait and retry

---

### 3.3 ImageFetcher Module

**Purpose:** Find relevant images for articles

**Inputs:**
- Keywords (from topic/article)
- Count (default: 5)

**Outputs:**
```python
@dataclass
class Image:
    url: str
    alt_text: str
    source: str
    photographer: str
    is_featured: bool
```

**Logic:**
1. Extract main keywords from topic
2. Search Unsplash API
3. Select best matches (relevance + quality)
4. Generate SEO alt text
5. Mark first as featured image

**Error Handling:**
- No results: Try broader keywords
- API limit: Use cached images or skip

---

### 3.4 QualityChecker Module

**Purpose:** Validate article quality before publishing

**Inputs:**
- Article object
- Target keywords

**Outputs:**
```python
@dataclass
class QualityReport:
    status: QualityStatus  # PASS/FAIL
    word_count: int
    keyword_density: float
    heading_count: dict
    image_count: int
    issues: List[str]
    suggestions: List[str]
```

**Validation Rules:**

| Rule | Min | Target | Max | Weight |
|------|-----|--------|-----|--------|
| Word Count | 1500 | 2000 | 5000 | 30% |
| Keyword Density | 0.5% | 1.5% | 2.5% | 20% |
| H2 Headings | 4 | 6 | 10 | 15% |
| H3 Headings | 2 | 4 | 15 | 10% |
| Images | 3 | 5 | 10 | 15% |
| Meta Description | 120 | 150 | 160 | 10% |

**Pass Threshold:** 70% weighted score

---

### 3.5 WordPressClient Module

**Purpose:** Publish articles to WordPress

**Inputs:**
- Article object
- Status (draft/publish)
- Categories
- Tags

**Outputs:**
```python
@dataclass
class PublishResult:
    success: bool
    post_id: int
    post_url: str
    error: Optional[str]
```

**API Operations:**
1. Upload featured image
2. Create post with content
3. Set categories (create if needed)
4. Set tags (create if needed)
5. Return post URL

**Error Handling:**
- Auth failure: Fatal, stop pipeline
- Upload failure: Retry 3x
- Post failure: Log and notify

---

### 3.6 Notifier Module

**Purpose:** Send alerts and summaries

**Inputs:**
- Pipeline result
- List of articles
- Any errors

**Outputs:**
- Email sent (success/failure)

**Email Templates:**

**Success:**
```
Subject: WP Auto Blog: 3 articles created

Pipeline completed at 2026-01-02 06:15

Summary:
- Topics detected: 15
- Articles created: 3
- Articles published: 3

Articles:
1. [DRAFT] Best AI Tools 2026
   URL: https://yourblog.com/?p=123

2. [DRAFT] Claude 3.5 Review
   URL: https://yourblog.com/?p=124

3. [DRAFT] GPT-5 Rumors
   URL: https://yourblog.com/?p=125

Review and publish at: https://yourblog.com/wp-admin/
```

**Error:**
```
Subject: [ERROR] WP Auto Blog Pipeline Failed

Pipeline failed at 2026-01-02 06:10

Error: WordPress API authentication failed
Details: 401 Unauthorized

Please check:
1. WP_USERNAME in .env
2. WP_APP_PASSWORD in .env
3. Application password is active in WordPress
```

---

## 4. Data Models

### 4.1 Core Entities

See `data-model.md` for full specifications:
- Topic
- Article
- Image
- QualityReport
- PublishResult
- PipelineRun

### 4.2 Configuration

**Environment Variables (.env):**
```bash
# WordPress
WP_SITE_URL=https://yourblog.com
WP_USERNAME=admin
WP_APP_PASSWORD=xxxx-xxxx-xxxx

# AI APIs
GEMINI_API_KEY=your-key
OPENAI_API_KEY=your-key

# Images
UNSPLASH_ACCESS_KEY=your-key

# Notifications
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email
SMTP_PASSWORD=your-password
NOTIFY_EMAIL=recipient

# Pipeline
PIPELINE_TOPICS_PER_RUN=3
PIPELINE_DEFAULT_STATUS=draft
```

---

## 5. CLI Commands

### 5.1 Available Commands

```bash
# Full pipeline
python -m src.main run [OPTIONS]
  --topics, -t    Number of topics to process (default: 3)
  --status, -s    Post status: draft/publish (default: draft)
  --dry-run       Simulate without publishing
  --source        Trend source: google/hn/all (default: all)

# Trend detection only
python -m src.main trends [OPTIONS]
  --source        Source: google/hn/all
  --limit, -l     Number of trends (default: 10)

# Generate single article
python -m src.main generate [OPTIONS]
  --topic         Topic to write about (required)
  --type          Article type: review/guide/list/comparison/news
  --output, -o    Output file (optional)

# Quality check
python -m src.main check [OPTIONS]
  --file          HTML file to check (required)
  --keywords      Target keywords (comma-separated)

# Test connections
python -m src.main test-wp       # Test WordPress API
python -m src.main test-ai       # Test AI providers
python -m src.main test-images   # Test image providers
```

### 5.2 Example Usage

```bash
# Daily scheduled run
python -m src.main run --topics 3

# Test with single article
python -m src.main run --topics 1 --dry-run

# Generate specific article
python -m src.main generate --topic "Best AI Coding Tools" --type list

# Check article quality
python -m src.main check --file output.html --keywords "ai,coding,tools"
```

---

## 6. Acceptance Criteria

### 6.1 Functional Requirements

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-01 | Detect trends | Returns 10+ topics from Google Trends + HN |
| FR-02 | Generate content | Creates 1500+ word HTML article |
| FR-03 | Fetch images | Returns 3+ relevant images with alt text |
| FR-04 | Quality check | Correctly identifies pass/fail articles |
| FR-05 | Publish to WP | Creates draft post with featured image |
| FR-06 | Send email | Delivers summary after pipeline run |
| FR-07 | CLI works | All commands execute without errors |

### 6.2 Non-Functional Requirements

| ID | Requirement | Target | Measurement |
|----|-------------|--------|-------------|
| NFR-01 | Trend detection speed | < 5 min | Timer |
| NFR-02 | Article generation speed | < 2 min/article | Timer |
| NFR-03 | Full pipeline speed | < 15 min | Timer |
| NFR-04 | Error recovery | 3 retries | Logs |
| NFR-05 | Log retention | 7 days | File count |
| NFR-06 | Uptime | 99% | Monitoring |

---

## 7. Testing Plan

### 7.1 Unit Tests

| Module | Test Cases |
|--------|------------|
| TrendDetector | API mock, scoring, dedup |
| ContentGenerator | Prompt loading, API mock, parsing |
| ImageFetcher | API mock, alt text generation |
| QualityChecker | All validation rules |
| WordPressClient | Auth, CRUD operations |
| Notifier | Email formatting |

### 7.2 Integration Tests

```python
def test_full_pipeline_dry_run():
    """Test complete pipeline without publishing"""
    result = run_pipeline(topics=1, dry_run=True)
    assert result.status == "completed"
    assert len(result.articles) == 1
    assert result.articles[0].word_count >= 1500

def test_wordpress_publish():
    """Test actual WordPress publishing"""
    article = create_test_article()
    result = wordpress_client.publish(article, status="draft")
    assert result.success
    assert result.post_url is not None
```

### 7.3 Manual Testing Checklist

```
[ ] Run pipeline with --dry-run
[ ] Verify trend detection from both sources
[ ] Check generated article quality manually
[ ] Test WordPress draft creation
[ ] Verify email notification received
[ ] Test error scenarios (invalid API key)
[ ] Confirm logs are written correctly
```

---

## 8. Development Timeline

### Week 1: Core Infrastructure

| Day | Tasks |
|-----|-------|
| 1 | Project setup, dependencies, folder structure |
| 2 | Config management, logging setup |
| 3-4 | TrendDetector module (Google Trends + HN) |
| 5 | Unit tests for TrendDetector |

### Week 2: Content Pipeline

| Day | Tasks |
|-----|-------|
| 1-2 | ContentGenerator module (Gemini + OpenAI) |
| 3 | ImageFetcher module (Unsplash) |
| 4 | QualityChecker module |
| 5 | Unit tests for all modules |

### Week 3: Publishing & Integration

| Day | Tasks |
|-----|-------|
| 1-2 | WordPressClient module |
| 3 | Notifier module (email) |
| 4 | CLI interface (typer) |
| 5 | Integration testing, bug fixes |

---

## 9. Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| pytrends API breaks | Medium | High | Fallback to HN only |
| Gemini rate limit | Low | Medium | Fallback to GPT-4o-mini |
| Low quality output | Medium | High | Strict quality checks |
| WordPress API issues | Low | High | Retry logic, notifications |

---

## 10. Success Metrics

| Metric | Week 1 | Week 4 | Week 8 |
|--------|--------|--------|--------|
| Articles/week | 7 | 14 | 21 |
| Avg. quality score | 70% | 80% | 85% |
| Pipeline uptime | 90% | 95% | 99% |
| Manual intervention | 50% | 20% | 10% |

---

*Document generated by System Designer Agent*
*Date: 2026-01-02*
*Version: 1.0*
