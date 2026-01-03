"""Trend Detector module for discovering hot topics.

Collects trending topics from multiple sources:
- Google Trends
- Hacker News
- Reddit

FR-001: Trend Detection
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import requests
from loguru import logger

# Post registry base directory
POST_REGISTRY_DIR = Path(__file__).parent.parent / "data"


def get_registry_path(mode: str) -> Path:
    """Get the registry file path for a specific mode."""
    return POST_REGISTRY_DIR / f"post_registry_{mode}.json"

try:
    from pytrends.request import TrendReq
except ImportError:
    TrendReq = None  # type: ignore

try:
    import praw
except ImportError:
    praw = None  # type: ignore

# Claude Agent SDK for LLM-based topic analysis
try:
    from claude_agent_sdk import query as claude_agent_query
    import asyncio
    CLAUDE_SDK_AVAILABLE = True
except ImportError:
    claude_agent_query = None
    asyncio = None
    CLAUDE_SDK_AVAILABLE = False


class TrendSource(Enum):
    """Enumeration of trend sources."""

    GOOGLE_TRENDS = "google_trends"
    HACKER_NEWS = "hacker_news"
    REDDIT = "reddit"


@dataclass
class Topic:
    """Represents a trending topic.

    Attributes:
        topic: The topic title/name
        keywords: List of relevant keywords
        source: Where the topic was found
        score: Relevance score (0-100)
        suggested_title: SEO-friendly blog title suggestion
        category: LLM-analyzed category (optional, used instead of auto-detect)
    """

    topic: str
    keywords: list[str]
    source: TrendSource
    score: int
    suggested_title: str
    category: Optional[str] = None  # LLM이 분석한 카테고리

    def to_dict(self) -> dict:
        """Convert Topic to dictionary."""
        return {
            "topic": self.topic,
            "keywords": self.keywords,
            "source": self.source.value,
            "score": self.score,
            "suggested_title": self.suggested_title,
            "category": self.category,
        }


class TrendMode(Enum):
    """Trend detection mode."""

    GENERAL = "general"  # Hot topics EXCLUDING tech (lifestyle, business, entertainment)
    TECH = "tech"  # Tech/programming focused only
    ALL = "all"  # Everything including tech and general


@dataclass
class TrendConfig:
    """Configuration for trend detection.

    Attributes:
        min_score: Minimum score threshold (0-100)
        max_topics: Maximum number of topics to return
        mode: TrendMode.GENERAL for hot topics, TrendMode.TECH for tech-focused
        niche_keywords: Keywords defining the niche (auto-set based on mode)
        hn_limit: Number of HN stories to fetch
        reddit_subreddits: Subreddits to monitor (auto-set based on mode)
        reddit_limit: Posts per subreddit
        enable_google_trends: Enable Google Trends (deprecated, may not work)
    """

    min_score: int = 20  # Lower threshold for general hot topics
    max_topics: int = 10
    mode: TrendMode = TrendMode.GENERAL  # Default: general hot topics
    enable_google_trends: bool = False  # Disabled by default (pytrends deprecated)
    niche_keywords: list[str] = field(default_factory=list)
    hn_limit: int = 50  # More stories for better coverage
    reddit_subreddits: list[str] = field(default_factory=list)
    reddit_limit: int = 15

    def __post_init__(self):
        """Set keywords and subreddits based on mode if not provided."""
        if not self.niche_keywords:
            self.niche_keywords = self._get_keywords_for_mode()
        if not self.reddit_subreddits:
            self.reddit_subreddits = self._get_subreddits_for_mode()

    def _get_keywords_for_mode(self) -> list[str]:
        """Get keywords based on trend mode."""
        if self.mode == TrendMode.TECH:
            # Tech-only keywords
            return [
                "ai", "artificial intelligence", "machine learning",
                "automation", "developer", "programming", "code",
                "tech", "saas", "startup", "software", "api",
                "cloud", "devops", "frontend", "backend", "app",
                "github", "open source", "framework", "database",
            ]
        elif self.mode == TrendMode.GENERAL:
            # Non-tech hot topics (EXCLUDE tech)
            return [
                # Viral/trending indicators
                "breaking", "viral", "trending", "popular", "best",
                "top", "new", "latest", "update", "announced",
                # Lifestyle & wellness
                "health", "fitness", "wellness", "lifestyle", "travel",
                "food", "recipe", "diet", "self-improvement",
                # Business & money (non-tech)
                "money", "finance", "investing", "career", "job",
                "business", "economy", "market", "real estate",
                # Entertainment
                "movie", "music", "celebrity", "entertainment", "sports",
                "gaming", "netflix", "streaming",
                # General interest
                "science", "space", "environment", "education",
            ]
        # ALL mode - everything
        return [
            "breaking", "viral", "trending", "popular", "best",
            "ai", "tech", "money", "health", "science",
            "business", "startup", "innovation", "future",
            "how to", "guide", "tips", "review", "comparison",
        ]

    def _get_subreddits_for_mode(self) -> list[str]:
        """Get subreddits based on trend mode."""
        if self.mode == TrendMode.TECH:
            # Tech-only subreddits
            return [
                "technology", "programming", "artificial",
                "MachineLearning", "webdev", "startups",
                "Python", "javascript", "devops", "opensource",
            ]
        elif self.mode == TrendMode.GENERAL:
            # Non-tech subreddits (EXCLUDE tech)
            return [
                # General hot topics
                "popular", "news", "worldnews",
                # Lifestyle & interests
                "LifeProTips", "todayilearned", "GetMotivated",
                "selfimprovement", "productivity",
                # Business & money
                "business", "Entrepreneur", "PersonalFinance",
                "investing", "RealEstate",
                # Entertainment & viral
                "movies", "television", "Music", "sports",
                # Health & wellness
                "Fitness", "nutrition", "science",
            ]
        # ALL mode - everything
        return [
            "popular", "all", "news", "worldnews",
            "technology", "programming", "MachineLearning",
            "LifeProTips", "todayilearned", "Futurology",
            "business", "Entrepreneur", "PersonalFinance",
            "movies", "television", "gaming",
        ]


class TrendDetector:
    """Detects trending topics from multiple sources.

    Example:
        >>> detector = TrendDetector()
        >>> topics = detector.collect()
        >>> for topic in topics:
        ...     print(f"{topic.topic} (score: {topic.score})")
    """

    HN_API_BASE = "https://hacker-news.firebaseio.com/v0"

    # Category detection keywords (order matters - first match wins)
    # TrendPulse.blog 사일로 구조: 테크, 비즈니스, 생산성, 리뷰, 건강
    CATEGORY_KEYWORDS = {
        # === trendpulse.blog (Korean) - 한국어 카테고리 ===

        # 건강: 웰니스/바이오해킹 트렌드 (YMYL 피하고 트렌드 관점)
        # 나쁜 예: "당뇨병 치료법" / 좋은 예: "실리콘밸리 CEO 단식 트렌드"
        "건강": [
            "바이오해킹", "biohacking", "누트로픽", "nootropic",
            "웰니스", "wellness", "웰빙",
            "단식", "간헐적단식", "fasting",
            "뇌효율", "집중력", "인지기능",
            "수면해킹", "수면루틴",
            "명상", "마인드풀니스", "mindfulness",
            "콜드플런지", "냉수샤워", "사우나",
            "장건강", "마이크로바이옴", "프로바이오틱스",
            "실리콘밸리", "테크CEO", "루틴",
        ],

        # 생산성: 업무 툴, 자기계발, 생산성 팁 (체류시간 증대)
        "생산성": [
            "생산성", "업무효율", "업무자동화", "자동화", "효율", "시간관리",
            "노션", "Notion", "템플릿", "워크플로우",
            "자기계발", "습관", "루틴", "목표", "성장",
            "원격근무", "재택", "재택근무", "홈오피스", "데스크세팅", "데스크 세팅",
            "협업툴", "업무툴", "업무환경",
            "productivity", "workflow", "automation", "habit", "home office", "desk setup",
            "ChatGPT 활용", "AI 활용", "GPT 활용",
        ],

        # 리뷰: IT 기기 + 건강 보조 기구 (직접적인 수익 - 제휴 마케팅)
        # 구매 직전 사람들이 검색 → 전환율 높음
        "리뷰": [
            "리뷰", "언박싱", "사용기", "후기", "개봉기",
            "가성비", "순위", "랭킹", "vs",
            "노트북", "스마트폰", "태블릿", "모니터", "키보드", "마우스",
            "데스크테리어", "스마트홈", "가젯", "기기",
            "review", "setup", "unboxing",
            # 건강 보조 기구 (리뷰 카테고리에서 다룸)
            "마사지건", "안마기", "거북목", "자세교정",
            "스탠딩데스크", "모션데스크", "인체공학",
            "애플워치", "갤럭시워치", "핏빗",
            "추천", "비교", "베스트", "TOP",  # 범용 키워드는 뒤로
        ],

        # 비즈니스: 기업 분석, 마케팅, 경제 이슈 해설 (브랜딩)
        "비즈니스": [
            "기업", "회사", "전략", "마케팅", "브랜드",
            "산업", "트렌드", "미래", "전망", "분석",
            "스타트업", "창업", "비즈니스", "경영",
            "취업", "이직", "커리어", "직업", "취준",
            "애플", "삼성", "구글", "테슬라", "아마존", "메타",
            "반도체", "배터리", "전기차", "로봇",
            "business", "strategy", "industry", "career",
        ],

        # 테크: AI + 헬스테크/슬립테크 (트래픽 유입, 높은 애드센스 단가)
        # 전략: "이 기술이 우리 삶(건강/생산성)을 어떻게 바꾸나" 관점
        "테크": [
            "AI", "인공지능", "ChatGPT", "GPT", "LLM", "Claude", "Gemini",
            "머신러닝", "딥러닝", "생성형",
            "신기술", "테크", "출시", "업데이트", "발표",
            "개발", "코딩", "프로그래밍", "API", "오픈소스",
            "영상편집", "이미지생성", "음성합성",
            "artificial intelligence", "machine learning",
            # 헬스테크/슬립테크 (테크 관점에서 다룸)
            "슬립테크", "sleep tech", "헬스테크", "health tech",
            "웨어러블", "wearable", "스마트워치", "오라링", "Oura",
            "수면측정", "심박변이", "HRV",
            "AI영양제", "맞춤영양", "개인화건강",
        ],

        # 취업: 외항사/항공사 취업 정보 (면접, 기출문제, 채용일정)
        "취업": [
            "취업", "면접", "자소서", "자기소개서", "이력서",
            "채용", "공채", "경력직", "신입", "합격",
            # 외항사/항공사 특화
            "외항사", "항공사", "승무원", "객실승무원", "캐빈크루",
            "에미레이트", "싱가포르항공", "카타르항공", "에티하드",
            "대한항공", "아시아나", "진에어", "제주항공", "티웨이",
            "기출문제", "족보", "면접후기", "합격후기",
            "토익", "오픽", "영어면접", "인적성", "적성검사",
            "채용일정", "시험일자", "경쟁률", "TO", "채용인원",
        ],

        # === bytepulse.io (English) ===
        "AI Tools": [
            "AI tool", "LLM", "GPT", "Claude", "Gemini", "Copilot",
            "automation", "AI assistant", "chatbot",
        ],
        "Dev Productivity": [
            "developer", "IDE", "VS Code", "vim", "workflow",
            "productivity", "coding", "programming",
        ],
        "SaaS Reviews": [
            "SaaS", "software review", "platform", "service",
            "pricing", "alternative",
        ],
    }

    @classmethod
    def detect_category(cls, topic: str, mode: str = "general") -> str:
        """Detect appropriate category based on topic keywords.

        TrendPulse.blog 우선순위: 건강 > 생산성 > 리뷰 > 비즈니스 > 테크

        Args:
            topic: Topic title to analyze
            mode: 'general' for trendpulse.blog (Korean), 'tech' for bytepulse.io

        Returns:
            Category name (e.g., "테크", "비즈니스", "생산성", "리뷰", "건강")
        """
        topic_lower = topic.lower()

        if mode == "general":
            # Korean blog - TrendPulse 컨셉: "더 나은 나를 위한 트렌드와 도구들"
            # 생산성(수익효율) > 리뷰(현금) > 테크(트래픽) > 비즈니스(권위) > 건강(웰니스) > 취업(외항사)
            priority_order = ["생산성", "리뷰", "테크", "비즈니스", "건강", "취업"]
        else:
            # English tech blog
            priority_order = ["AI Tools", "Dev Productivity", "SaaS Reviews"]

        for category in priority_order:
            if category not in cls.CATEGORY_KEYWORDS:
                continue
            for keyword in cls.CATEGORY_KEYWORDS[category]:
                if keyword.lower() in topic_lower:
                    logger.debug(f"Category detected: {category} (matched: {keyword})")
                    return category

        # Default fallback
        return "테크" if mode == "general" else "AI Tools"
    STOP_WORDS = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "must", "shall", "can", "need", "dare",
        "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
        "into", "through", "during", "before", "after", "above", "below",
        "between", "under", "again", "further", "then", "once", "here",
        "there", "when", "where", "why", "how", "all", "each", "few",
        "more", "most", "other", "some", "such", "no", "nor", "not",
        "only", "own", "same", "so", "than", "too", "very", "just",
        "and", "but", "if", "or", "because", "until", "while", "this",
        "that", "these", "those", "i", "me", "my", "myself", "we", "our",
        "you", "your", "he", "him", "his", "she", "her", "it", "its",
        "they", "them", "their", "what", "which", "who", "whom",
        "new", "show", "hn", "ask",
    }

    def __init__(self, config: Optional[TrendConfig] = None) -> None:
        """Initialize TrendDetector.

        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or TrendConfig()
        self._setup_reddit()

    def _setup_reddit(self) -> None:
        """Setup Reddit API client if credentials available."""
        self._reddit = None
        if praw is None:
            logger.warning("praw not installed, Reddit fetching disabled")
            return

        client_id = os.getenv("REDDIT_CLIENT_ID")
        client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        user_agent = os.getenv("REDDIT_USER_AGENT", "wp-auto-blog/1.0")

        if client_id and client_secret:
            try:
                self._reddit = praw.Reddit(
                    client_id=client_id,
                    client_secret=client_secret,
                    user_agent=user_agent,
                )
                logger.info("Reddit API client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Reddit client: {e}")

    def collect(self) -> list[Topic]:
        """Collect trending topics from all sources.

        Returns:
            List of Topic objects, sorted by score (descending),
            filtered by min_score and limited to max_topics.
        """
        logger.info("Collecting trends from all sources...")

        all_topics = self._fetch_all_sources()

        # Filter by minimum score
        filtered = [t for t in all_topics if t.score >= self.config.min_score]
        logger.debug(f"Filtered {len(all_topics)} -> {len(filtered)} topics (min_score={self.config.min_score})")

        # Sort by score descending
        sorted_topics = sorted(filtered, key=lambda t: t.score, reverse=True)

        # Limit to max_topics
        result = sorted_topics[: self.config.max_topics]
        logger.info(f"Returning {len(result)} topics")

        return result

    def collect_with_llm(self, use_llm: bool = True) -> list[Topic]:
        """Collect topics and optionally filter/prioritize with LLM.

        TrendPulse 컨셉에 맞는 토픽을 LLM이 분석하여 추천합니다:
        - 한국 시장에 맞는 토픽 필터링
        - 카테고리별 최적 토픽 추천
        - 수익화 가능성 평가

        Args:
            use_llm: Whether to use LLM for analysis (default: True)

        Returns:
            List of recommended Topic objects
        """
        # First, collect topics from sources
        raw_topics = self.collect()

        if not use_llm or not CLAUDE_SDK_AVAILABLE:
            logger.info("LLM analysis skipped (disabled or SDK unavailable)")
            return raw_topics

        if not raw_topics:
            logger.warning("No topics to analyze")
            return raw_topics

        logger.info(f"Analyzing {len(raw_topics)} topics with LLM...")

        try:
            analyzed = self._analyze_topics_with_llm(raw_topics)
            if analyzed:
                return analyzed
            else:
                logger.warning("LLM analysis returned no results, using raw topics")
                return raw_topics
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}, using raw topics")
            return raw_topics

    def _load_existing_posts(self) -> list[str]:
        """Load existing post titles from mode-specific registry for duplicate detection.

        Returns:
            List of existing post titles for the current mode
        """
        # Get mode-specific registry path
        mode_str = self.config.mode.value  # "general" or "tech"
        registry_path = get_registry_path(mode_str)

        if not registry_path.exists():
            return []

        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                posts = json.load(f)

            existing_titles = []
            for post in posts:
                title = post.get("title", "")
                topic = post.get("topic", "")
                if title:
                    existing_titles.append(title)
                if topic and topic != title:
                    existing_titles.append(topic)

            return existing_titles
        except Exception as e:
            logger.warning(f"Failed to load existing posts: {e}")
            return []

    def _analyze_topics_with_llm(self, topics: list[Topic]) -> list[Topic]:
        """Use LLM to analyze and prioritize topics.

        Args:
            topics: List of raw topics to analyze

        Returns:
            Filtered and prioritized list of topics
        """
        # Prepare topic list for LLM
        topic_list = "\n".join([
            f"{i+1}. [{t.source.value}] {t.topic} (score: {t.score})"
            for i, t in enumerate(topics[:20])  # Max 20 topics
        ])

        # Load existing posts for duplicate detection
        existing_posts = self._load_existing_posts()
        existing_posts_section = ""

        # Use different prompt based on mode
        if self.config.mode == TrendMode.TECH:
            prompt = self._build_tech_mode_prompt(topic_list, existing_posts)
        else:
            prompt = self._build_general_mode_prompt(topic_list, existing_posts)

        try:
            # Call Claude Agent SDK
            logger.info("Topic analysis using: Claude Agent SDK (OAuth)")
            result = self._call_claude_sdk(prompt)
            if not result:
                return []

            # Parse LLM response and match with original topics
            # Tech mode uses English titles, general mode uses Korean
            is_tech_mode = self.config.mode == TrendMode.TECH
            recommended = self._parse_llm_recommendations(result, topics, english_mode=is_tech_mode)
            logger.info(f"LLM recommended {len(recommended)} topics")
            return recommended

        except Exception as e:
            logger.error(f"LLM topic analysis error: {e}")
            return []

    def _build_general_mode_prompt(self, topic_list: str, existing_posts: list[str]) -> str:
        """Build LLM prompt for general mode (TrendPulse.blog - Korean).

        Args:
            topic_list: Formatted list of topics
            existing_posts: List of existing post titles for duplicate detection

        Returns:
            Prompt string for LLM
        """
        existing_posts_section = ""
        if existing_posts:
            existing_list = "\n".join([f"- {title}" for title in existing_posts[:20]])
            existing_posts_section = f"""
## ⚠️ 이미 발행된 포스트 (중복 제외 필수!)
다음 주제와 **의미적으로 유사한 토픽은 절대 추천하지 마세요**:
{existing_list}

예시:
- "POSSE 전략" ≈ "내 사이트 우선 발행" ≈ "콘텐츠 신디케이션" → 중복!
- "텍스트 가계부" ≈ "메모장 가계부" ≈ "플레인텍스트 재무관리" → 중복!
- "스탠딩데스크 추천" ≈ "스탠딩데스크 비교" ≈ "서서 일하기" → 중복!

"""

        return f"""당신은 TrendPulse 블로그의 콘텐츠 전략가입니다.
{existing_posts_section}

## TrendPulse 컨셉
"더 나은 나를 위한 트렌드와 도구들"
- 생산성: 더 똑똑하게 일하고
- 리뷰/테크: 최신 도구를 활용하며
- 웰니스: 최상의 컨디션을 유지하는 법

## 카테고리 우선순위 (수익 효율 순)
1. 생산성 - 노션 템플릿, SaaS 제휴
2. 리뷰 - 쿠팡 파트너스, 제휴 마케팅
3. 테크 - 높은 애드센스 단가, 헬스테크 포함
4. 비즈니스 - 브랜딩, 권위
5. 건강 - 바이오해킹/웰니스/슬립테크 트렌드 (생산성 향상 관점 OK, 의료 조언만 제외)
6. 취업 - 외항사/항공사 면접, 기출문제, 채용일정, 합격후기

## 분석할 토픽들
{topic_list}

## 요청사항
위 토픽들 중에서 TrendPulse에 적합한 토픽 5개를 추천해주세요.

각 토픽에 대해 다음 형식으로 답변:
[순위]. [토픽제목]
- 카테고리: [하나만 선택: 생산성 | 리뷰 | 테크 | 비즈니스 | 건강 | 취업]
- 한국어 제목 제안: [SEO 최적화된 한국어 제목]
- 추천 이유: [1줄 설명]

중요: 카테고리는 반드시 하나만 선택! "생산성/테크" 같은 복합 카테고리 금지.

## 한국어 제목 작성 규칙 (구글 SEO 최적화)

3가지 유형 중 가장 적합한 것을 선택:

[유형 1: 효용 강조형] - 뉴스레터/피드용
- 구체적 숫자(%, 금액, 년수)와 독자가 얻을 이익(Benefit) 강조
- 예: "10년간 앱 없이 1억 모은 개발자의 가계부 비법"

[유형 2: 트렌드 분석형] - 전문 칼럼용
- 현재 연도(2026)와 최신 트렌드 키워드 반영
- 예: "2026년 디지털 미니멀리즘, 왜 개발자들은 앱을 버리나"

[유형 3: SEO/직관형] - 구글 검색 노출용
- 검색 사용자가 입력할 핵심 키워드 포함, 주제 명확히 요약
- 예: "텍스트 가계부 사용법 완벽 가이드 (개발자 10년 노하우)"

※ 규칙: 30-50자, 이모지 없이 텍스트만

주의:
- 주식/투자 관련 토픽 제외
- 한국 독자에게 관련 없는 토픽 제외
- 의료 조언/약물 추천/질병 치료법 토픽만 제외 (YMYL 위험)
- 바이오해킹, 웰니스, 슬립테크, 생산성 향상 관점의 건강 토픽은 ✅ 허용
- 수익화 가능성이 높은 토픽 우선"""

    def _build_tech_mode_prompt(self, topic_list: str, existing_posts: list[str]) -> str:
        """Build LLM prompt for tech mode (BytePulse.io - English).

        Focuses on VS comparisons, Migration guides, and high-intent purchase keywords
        for developer/startup audience with recurring commission potential.

        Args:
            topic_list: Formatted list of topics
            existing_posts: List of existing post titles for duplicate detection

        Returns:
            Prompt string for LLM
        """
        existing_posts_section = ""
        if existing_posts:
            existing_list = "\n".join([f"- {title}" for title in existing_posts[:20]])
            existing_posts_section = f"""
## ⚠️ Already Published Posts (MUST EXCLUDE duplicates!)
Do NOT recommend topics semantically similar to these:
{existing_list}

Examples of duplicates:
- "Cursor vs Copilot" ≈ "Copilot alternatives" ≈ "Best AI code editor" → DUPLICATE!
- "Migrate to Linear" ≈ "Linear tutorial" ≈ "Jira alternative" → DUPLICATE!

"""

        return f"""You are the content strategist for BytePulse.io, a tech blog targeting developers and startup founders.
{existing_posts_section}

## BytePulse.io Mission
Help developers and startup founders make BUYING DECISIONS.
NOT just information - guide them to ACTION (signup, purchase, migrate).

## Content Type Priority (50%+ MUST be VS/Comparison)
1. **VS Comparisons** (HIGHEST PRIORITY - 50%+): Tool A vs Tool B
   - Examples: "Cursor vs GitHub Copilot 2026", "Linear vs Jira for Startups"
   - WHY: High purchase intent, easy affiliate conversion

2. **Migration Guides** (HIGH PRIORITY - 30%):
   - Examples: "How to Migrate from Jira to Linear", "Switching from VS Code to Cursor"
   - WHY: Users ready to switch = ready to buy

3. **Tool Deep Dives** (20%):
   - Examples: "Webflow for Developers: Complete Guide 2026"
   - WHY: Recurring commission potential

## High-Value VS Keywords to Prioritize
- AI Code Editors: Cursor, Copilot, Codeium, Tabnine, Windsurf
- Project Management: Linear, Jira, Notion, Height, Shortcut
- Design/NoCode: Webflow, Framer, Figma, Canva
- Dev Tools: Vercel, Netlify, Railway, Render
- AI Tools: Claude, ChatGPT, Gemini, Perplexity

## Tools with Recurring Commission (PRIORITIZE)
- Webflow, Semrush, Notion, Ahrefs, Surfer SEO
- Vercel Pro, Railway, Render
- Cursor Pro, GitHub Copilot

## Topics to Analyze
{topic_list}

## Request
From the topics above, recommend 5 topics suitable for BytePulse.io.

Format your response EXACTLY like this:
[Rank]. [Original Topic]
- Category: [Pick ONE: AI Tools | Dev Productivity | SaaS Reviews]
- Suggested Title: [SEO-optimized ENGLISH title under 60 chars]
- Content Type: [VS Comparison/Migration Guide/Tool Review]
- Monetization: [Affiliate opportunity or AdSense potential]
- Reason: [1-line explanation]

IMPORTANT: Category must be EXACTLY ONE of: "AI Tools", "Dev Productivity", or "SaaS Reviews". Do NOT combine them.

## English Title Rules (Google SEO Optimized)
- Include year (2026) for freshness
- Use VS format when comparing: "X vs Y: Which is Better in 2026?"
- Use "How to" for migration: "How to Migrate from X to Y (Step-by-Step)"
- Keep under 60 characters
- Include primary keyword at the beginning

## IMPORTANT Rules
- At least 3 out of 5 topics MUST be VS comparisons
- Prioritize tools with recurring affiliate commission
- English titles only (global market)
- Focus on purchase-intent keywords
- Avoid pure news/announcements (low conversion)
- Avoid topics requiring code examples that need verification"""

    def _call_claude_sdk(self, prompt: str) -> str:
        """Call Claude Agent SDK with prompt.

        Args:
            prompt: The prompt to send

        Returns:
            LLM response text
        """
        if not CLAUDE_SDK_AVAILABLE or claude_agent_query is None:
            raise RuntimeError("Claude Agent SDK not available")

        async def _async_query():
            messages = []
            async for msg in claude_agent_query(prompt=prompt):
                messages.append(msg)

            # Extract text from ResultMessage
            for msg in messages:
                if type(msg).__name__ == 'ResultMessage':
                    if hasattr(msg, 'result') and msg.result:
                        return msg.result

            # Fallback: try AssistantMessage.content
            for msg in messages:
                if type(msg).__name__ == 'AssistantMessage':
                    if hasattr(msg, 'content') and msg.content:
                        text_parts = []
                        for block in msg.content:
                            if hasattr(block, 'text'):
                                text_parts.append(block.text)
                        if text_parts:
                            return '\n'.join(text_parts)
            return ""

        return asyncio.run(_async_query())

    def _parse_llm_recommendations(
        self,
        llm_response: str,
        original_topics: list[Topic],
        english_mode: bool = False,
    ) -> list[Topic]:
        """Parse LLM recommendations and match with original topics.

        Args:
            llm_response: The LLM response text
            original_topics: Original topic list to match against
            english_mode: If True, parse English titles (tech mode)

        Returns:
            List of recommended topics with updated info
        """
        logger.debug(f"LLM Response:\n{llm_response[:500]}...")

        recommended = []
        lines = llm_response.split('\n')

        current_topic = None
        current_category = None
        current_title = None  # Renamed from current_korean_title

        def save_topic():
            """Helper to save current topic if valid."""
            nonlocal current_topic, current_category, current_title

            # Skip invalid titles (N/A, empty, etc.)
            if not current_title or current_title.upper() == "N/A":
                return

            # Skip only explicitly excluded topics (YMYL medical advice)
            # Allow: 건강, 바이오해킹, 웰니스 (without "제외")
            # Skip: "건강 (제외 권장)", "YMYL 제외" etc.
            if current_category and "제외" in current_category:
                logger.debug(f"Skipping YMYL excluded topic: {current_title}")
                return

            if current_title:
                # Find matching original topic or use first available
                matched_orig = None
                if current_topic:
                    # Try to match by keywords
                    topic_words = [w.lower() for w in current_topic.split() if len(w) > 2]
                    for orig in original_topics:
                        orig_lower = orig.topic.lower()
                        if any(word in orig_lower for word in topic_words):
                            matched_orig = orig
                            break

                # Fallback: use first unused original topic
                if not matched_orig and original_topics:
                    used_titles = {r.topic for r in recommended}
                    for orig in original_topics:
                        if orig.topic not in used_titles:
                            matched_orig = orig
                            break

                if matched_orig:
                    # Clean category (remove annotations like "(제외 권장)")
                    clean_category = None
                    if current_category:
                        clean_category = re.sub(r'\s*\([^)]*\)', '', current_category).strip()

                    # Extract keywords from the title
                    title_keywords = self._extract_keywords(current_title)

                    new_topic = Topic(
                        topic=current_title,
                        keywords=title_keywords if title_keywords else matched_orig.keywords,
                        source=matched_orig.source,
                        score=matched_orig.score + 10,
                        suggested_title=current_title,
                        category=clean_category,  # LLM이 분석한 카테고리 저장
                    )
                    recommended.append(new_topic)
                    logger.debug(f"Added topic: {current_title} (category: {clean_category})")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for topic line (e.g., "1. Topic Name", "1) Topic", "**[1위]. Topic**")
            # Patterns: "**[1위]. Topic", "1. Topic", "**1. Topic**", "1) Topic"
            topic_match = re.match(r'^[\*\#]*\s*\[?(\d+)[위]?\]?[\.\)\:]\s*(.+)', line)
            if topic_match:
                # Save previous topic first
                save_topic()

                # Reset for new topic
                current_topic = topic_match.group(2).strip().strip('*[]')
                current_category = None
                current_title = None
                logger.debug(f"Found topic line: {current_topic}")
                continue

            # Check for category line (various formats)
            if '카테고리' in line or 'Category' in line:
                cat_match = re.search(r'(?:카테고리|Category)[^:：]*[:：]\s*(.+)', line, re.IGNORECASE)
                if cat_match:
                    current_category = cat_match.group(1).strip().strip('*')
                    logger.debug(f"Found category: {current_category}")

            # Parse title based on mode
            if english_mode:
                # English mode: look for "Suggested Title:"
                if 'Suggested Title' in line or 'Title:' in line:
                    title_match = re.search(r'(?:Suggested\s+)?Title[^:：]*[:：]\s*(.+)', line, re.IGNORECASE)
                    if title_match:
                        title_text = title_match.group(1).strip()
                        # Remove surrounding quotes (various styles)
                        title_text = re.sub(r'^["\'"]+|["\'"]+$', '', title_text)
                        title_text = title_text.strip('*')
                        current_title = title_text.strip()
                        logger.debug(f"Found English title: {current_title}")
            else:
                # Korean mode: look for "한국어 제목 제안:"
                if '제목' in line and ('한국어' in line or '제안' in line or ':' in line or '：' in line):
                    title_match = re.search(r'(?:한국어\s*)?제목[^:：]*[:：]\s*(.+)', line)
                    if title_match:
                        title_text = title_match.group(1).strip().strip('"\'*「」')
                        # Remove type annotations like "(유형 1)", "(SEO)", etc.
                        title_text = re.sub(r'\s*\(유형\s*\d+\)', '', title_text)
                        title_text = re.sub(r'\s*\(SEO[^)]*\)', '', title_text)
                        title_text = re.sub(r'\s*\(효용[^)]*\)', '', title_text)
                        title_text = re.sub(r'\s*\(트렌드[^)]*\)', '', title_text)
                        current_title = title_text.strip()
                        logger.debug(f"Found Korean title: {current_title}")

        # Don't forget the last topic
        save_topic()

        logger.info(f"Parsed {len(recommended)} topics from LLM response")
        return recommended[:5]

    def _fetch_all_sources(self) -> list[Topic]:
        """Fetch topics from all configured sources.

        Returns:
            Combined list of topics from all sources.
        """
        topics: list[Topic] = []

        # Fetch from each source, handling errors gracefully
        topics.extend(self._fetch_hacker_news())
        topics.extend(self._fetch_google_trends())
        topics.extend(self._fetch_reddit())

        return topics

    def _fetch_hacker_news(self) -> list[Topic]:
        """Fetch trending topics from Hacker News.

        Returns:
            List of Topics from HN top stories.
        """
        topics: list[Topic] = []

        try:
            # Get top story IDs
            response = requests.get(
                f"{self.HN_API_BASE}/topstories.json",
                timeout=10,
            )
            response.raise_for_status()
            story_ids = response.json()[: self.config.hn_limit]

            # Fetch each story
            for story_id in story_ids:
                try:
                    story_resp = requests.get(
                        f"{self.HN_API_BASE}/item/{story_id}.json",
                        timeout=5,
                    )
                    story_resp.raise_for_status()
                    story = story_resp.json()

                    if not story or "title" not in story:
                        continue

                    title = story.get("title", "")
                    source_score = story.get("score", 0)

                    # Calculate relevance score
                    score = self._calculate_score(
                        title=title,
                        source_score=source_score,
                        source=TrendSource.HACKER_NEWS,
                    )

                    # Skip if not relevant enough
                    if score < 20:
                        continue

                    keywords = self._extract_keywords(title)
                    suggested_title = self._generate_title(title, keywords)

                    topics.append(
                        Topic(
                            topic=title,
                            keywords=keywords,
                            source=TrendSource.HACKER_NEWS,
                            score=score,
                            suggested_title=suggested_title,
                        )
                    )

                except Exception as e:
                    logger.debug(f"Failed to fetch HN story {story_id}: {e}")
                    continue

            logger.info(f"Fetched {len(topics)} topics from Hacker News")

        except Exception as e:
            logger.error(f"Failed to fetch Hacker News: {e}")

        return topics

    def _fetch_google_trends(self) -> list[Topic]:
        """Fetch trending topics from Google Trends.

        Note: As of April 2025, pytrends is deprecated and Google Trends
        API endpoints have changed. This feature may not work reliably.

        Returns:
            List of Topics from Google Trends.
        """
        topics: list[Topic] = []

        if not self.config.enable_google_trends:
            logger.debug("Google Trends disabled in config (pytrends deprecated)")
            return topics

        if TrendReq is None:
            logger.warning("pytrends not installed, skipping Google Trends")
            return topics

        try:
            pytrends = TrendReq(hl="en-US", tz=360)
            trending = pytrends.trending_searches(pn="united_states")

            for idx, row in trending.iterrows():
                if idx >= 20:  # Limit to 20
                    break

                title = str(row[0])
                keywords = self._extract_keywords(title)

                # Calculate score based on position (higher position = higher score)
                position_score = max(0, 100 - (idx * 5))

                score = self._calculate_score(
                    title=title,
                    source_score=position_score,
                    source=TrendSource.GOOGLE_TRENDS,
                )

                if score < 20:
                    continue

                suggested_title = self._generate_title(title, keywords)

                topics.append(
                    Topic(
                        topic=title,
                        keywords=keywords,
                        source=TrendSource.GOOGLE_TRENDS,
                        score=score,
                        suggested_title=suggested_title,
                    )
                )

            logger.info(f"Fetched {len(topics)} topics from Google Trends")

        except Exception as e:
            logger.error(f"Failed to fetch Google Trends: {e}")

        return topics

    def _fetch_reddit(self) -> list[Topic]:
        """Fetch trending topics from Reddit.

        Returns:
            List of Topics from configured subreddits.
        """
        topics: list[Topic] = []

        if self._reddit is None:
            logger.debug("Reddit client not available, skipping")
            return topics

        try:
            for subreddit_name in self.config.reddit_subreddits:
                try:
                    subreddit = self._reddit.subreddit(subreddit_name)
                    for submission in subreddit.hot(limit=self.config.reddit_limit):
                        title = submission.title
                        source_score = submission.score

                        score = self._calculate_score(
                            title=title,
                            source_score=source_score,
                            source=TrendSource.REDDIT,
                        )

                        if score < 20:
                            continue

                        keywords = self._extract_keywords(title)
                        suggested_title = self._generate_title(title, keywords)

                        topics.append(
                            Topic(
                                topic=title,
                                keywords=keywords,
                                source=TrendSource.REDDIT,
                                score=score,
                                suggested_title=suggested_title,
                            )
                        )

                except Exception as e:
                    logger.debug(f"Failed to fetch r/{subreddit_name}: {e}")
                    continue

            logger.info(f"Fetched {len(topics)} topics from Reddit")

        except Exception as e:
            logger.error(f"Failed to fetch Reddit: {e}")

        return topics

    def _calculate_score(
        self,
        title: str,
        source_score: int,
        source: TrendSource,
    ) -> int:
        """Calculate relevance score for a topic.

        Score is based on:
        - Source popularity (votes/upvotes)
        - Niche keyword relevance
        - Source weight

        Args:
            title: The topic title
            source_score: Raw score from source (votes, position, etc.)
            source: The source platform

        Returns:
            Score between 0 and 100
        """
        # Base score from source (normalize to 0-50)
        if source == TrendSource.HACKER_NEWS:
            # HN scores can range from 0 to 1000+
            base_score = min(50, source_score / 20)
        elif source == TrendSource.REDDIT:
            # Reddit scores can be very high
            base_score = min(50, source_score / 100)
        else:  # Google Trends
            # Already normalized position score
            base_score = min(50, source_score / 2)

        # Niche relevance bonus (0-50)
        title_lower = title.lower()
        relevance_score = 0
        for keyword in self.config.niche_keywords:
            if keyword.lower() in title_lower:
                relevance_score += 10

        relevance_score = min(50, relevance_score)

        # Combine scores
        total_score = int(base_score + relevance_score)

        # Clamp to 0-100
        return max(0, min(100, total_score))

    def _generate_title(self, topic: str, keywords: list[str]) -> str:
        """Generate SEO-friendly blog title.

        Args:
            topic: Original topic title
            keywords: Extracted keywords

        Returns:
            SEO-optimized title (max 70 characters)
        """
        # Title templates based on content type
        templates = [
            "{topic}: Complete Guide for {year}",
            "{topic} Review: Everything You Need to Know",
            "How to Use {topic}: A Beginner's Guide",
            "{topic} Explained: What You Should Know",
            "The Ultimate Guide to {topic}",
        ]

        # Clean the topic
        clean_topic = topic.strip()

        # Remove common prefixes
        prefixes_to_remove = ["Show HN:", "Ask HN:", "[D]", "[R]", "[P]"]
        for prefix in prefixes_to_remove:
            if clean_topic.startswith(prefix):
                clean_topic = clean_topic[len(prefix):].strip()

        # Use the first template for now (could be randomized or AI-generated later)
        from datetime import datetime
        year = datetime.now().year

        title = templates[0].format(topic=clean_topic, year=year)

        # Truncate if too long
        if len(title) > 70:
            title = title[:67] + "..."

        return title

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract keywords from text.

        Args:
            text: Input text

        Returns:
            List of keywords (max 5)
        """
        # Tokenize
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())

        # Remove stop words
        keywords = [w for w in words if w not in self.STOP_WORDS]

        # Get unique keywords, preserving order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)

        # Limit to 5
        return unique_keywords[:5]
