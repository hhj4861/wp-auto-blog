# WordPress Auto Blog Pipeline

AI 기반 자동 블로그 파이프라인 - 트렌드 감지부터 WordPress 발행까지 자동화

## Features

- **Trend Detection**: Google Trends, Hacker News, Reddit에서 핫 토픽 자동 수집
- **AI Content Generation**: Gemini/GPT-4o-mini로 SEO 최적화 블로그 글 생성
- **Image Fetching**: Unsplash/Pexels에서 관련 이미지 자동 첨부
- **WordPress Publishing**: REST API로 자동 발행 (Draft 또는 Publish)
- **TDD**: 80%+ 테스트 커버리지

## Project Structure

```
wp-auto-blog/
├── src/
│   ├── __init__.py
│   ├── config.py              # 설정 관리
│   ├── trend_detector.py      # 트렌드 감지 (FR-001)
│   ├── content_generator.py   # AI 콘텐츠 생성 (FR-002)
│   ├── image_fetcher.py       # 이미지 수집 (FR-003)
│   ├── wordpress_client.py    # WP API 클라이언트 (FR-005)
│   ├── pipeline.py            # 파이프라인 오케스트레이션
│   └── main.py                # CLI 진입점
├── tests/
│   ├── conftest.py            # pytest 설정
│   ├── test_trend_detector.py
│   ├── test_content_generator.py
│   ├── test_image_fetcher.py
│   ├── test_wordpress_client.py
│   └── test_integration.py
├── templates/
│   └── prompts/               # 프롬프트 템플릿
├── data/
│   ├── cache/                 # 키워드 캐시
│   ├── logs/                  # 로그 파일
│   └── coverage/              # 테스트 커버리지
├── scripts/
│   ├── setup.sh               # 설치 스크립트
│   └── test.sh                # 테스트 스크립트
├── .env.example
├── .gitignore
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Quick Start

### 1. Setup

```bash
# Clone and setup
cd wp-auto-blog
chmod +x scripts/*.sh
./scripts/setup.sh
```

### 2. Configure

Edit `.env` with your API keys:

```bash
# Required: At least one AI API
GOOGLE_AI_API_KEY=your_key
# OR
OPENAI_API_KEY=your_key

# Required: At least one image API
UNSPLASH_ACCESS_KEY=your_key
# OR
PEXELS_API_KEY=your_key

# Required: WordPress
WP_URL=https://your-blog.com
WP_USERNAME=your_username
WP_APP_PASSWORD=your_app_password
```

### 3. Run Tests

```bash
./scripts/test.sh
```

### 4. Run Pipeline

```bash
# Dry run (recommended first)
python -m src.main --dry-run

# Run with specific topic
python -m src.main --topic "Claude 3.5 Sonnet Review" --dry-run

# Full pipeline (creates drafts)
python -m src.main

# Auto-publish (not recommended initially)
python -m src.main --auto-publish
```

## CLI Usage

```
usage: main.py [-h] [--topic TOPIC] [--keywords KEYWORDS [KEYWORDS ...]]
               [--content-type {review,comparison,guide,list,news}]
               [--max-posts MAX_POSTS] [--category CATEGORY]
               [--auto-publish] [--dry-run] [-v]

options:
  --topic TOPIC         Specific topic (skips trend detection)
  --keywords            Keywords for the topic
  --content-type        Type of content (default: review)
  --max-posts           Maximum posts per run (default: 3)
  --category            WordPress category
  --auto-publish        Publish immediately
  --dry-run             Simulate without publishing
  -v, --verbose         Enable debug output
```

## Development

### TDD Workflow

```
RED    -> Write failing test
GREEN  -> Write minimal code to pass
REFACTOR -> Improve code quality
```

### Run Specific Tests

```bash
# Run unit tests only
python -m pytest tests/ -m unit

# Run integration tests
python -m pytest tests/ -m integration

# Run specific test file
python -m pytest tests/test_trend_detector.py -v

# Run with debug output
python -m pytest tests/ -v --tb=long
```

### Code Quality

```bash
# Type checking
python -m mypy src/

# Linting
python -m ruff check src/

# Format
python -m ruff format src/
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     BlogPipeline                            │
│                                                             │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐   │
│  │   Trend     │────▶│   Content   │────▶│   Image     │   │
│  │  Detector   │     │  Generator  │     │  Fetcher    │   │
│  └─────────────┘     └─────────────┘     └─────────────┘   │
│        │                   │                   │            │
│        ▼                   ▼                   ▼            │
│   Google Trends        Gemini            Unsplash          │
│   Hacker News          GPT-4o-mini       Pexels            │
│   Reddit                                                    │
│                                                             │
│                              │                              │
│                              ▼                              │
│                    ┌─────────────────┐                     │
│                    │   WordPress     │                     │
│                    │    Client       │                     │
│                    └─────────────────┘                     │
│                              │                              │
│                              ▼                              │
│                         WordPress                           │
│                        REST API                             │
└─────────────────────────────────────────────────────────────┘
```

## API Requirements

| Service | Purpose | Free Tier |
|---------|---------|-----------|
| Gemini | Content generation | 15 RPM |
| OpenAI | Backup content | $5 credit |
| Unsplash | Images | 50 req/hour |
| Pexels | Backup images | 200 req/hour |
| Reddit | Trends | 60 req/min |

## License

MIT
