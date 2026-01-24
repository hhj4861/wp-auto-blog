"""Content Generator module for AI-powered blog content creation.

Generates SEO-optimized blog posts using LLM APIs.

FR-002: Content Generation
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from loguru import logger

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None  # type: ignore
    genai_types = None  # type: ignore

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore

try:
    from claude_agent_sdk import query as claude_agent_query
    import asyncio
except ImportError:
    claude_agent_query = None  # type: ignore
    asyncio = None

import subprocess
import shutil

# Discount finder for K-Culture products
try:
    from .discount_finder import DiscountFinder, generate_discount_html
except ImportError:
    DiscountFinder = None
    generate_discount_html = None


class ContentType(Enum):
    """Types of blog content."""

    REVIEW = "review"
    COMPARISON = "comparison"
    GUIDE = "guide"
    LIST = "list"
    NEWS = "news"


class LLMProvider(Enum):
    """LLM API providers."""

    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OPENAI = "openai"


@dataclass
class GeneratedContent:
    """Represents generated blog content.

    Attributes:
        title: The blog post title
        html: Full HTML content
        meta_description: SEO meta description (150-160 chars)
        keywords: Target keywords
        word_count: Total word count
        content_type: Type of content generated
        focus_keyphrase: SEO focus keyphrase for Yoast (2-4 words)
    """

    title: str
    html: str
    meta_description: str
    keywords: list[str]
    word_count: int
    content_type: ContentType
    focus_keyphrase: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "html": self.html,
            "meta_description": self.meta_description,
            "keywords": self.keywords,
            "word_count": self.word_count,
            "content_type": self.content_type.value,
            "focus_keyphrase": self.focus_keyphrase,
        }


@dataclass
class ContentConfig:
    """Configuration for content generation.

    Attributes:
        min_words: Minimum word count
        max_words: Maximum word count
        provider: Primary LLM provider
        temperature: LLM temperature (0-1)
        model_gemini: Gemini model name
        model_openai: OpenAI model name
        language: Content language - 'ko' for Korean, 'en' for English
    """

    min_words: int = 800
    max_words: int = 1500
    provider: LLMProvider = LLMProvider.ANTHROPIC
    temperature: float = 0.7
    model_anthropic: str = "claude-sonnet-4-20250514"
    model_gemini: str = "gemini-2.0-flash-exp"
    model_openai: str = "gpt-4o-mini"
    use_cli: bool = True  # True: Claude CLI (OAuth), False: Anthropic API (key)
    language: str = "ko"  # 'ko' for Korean (general), 'en' for English (tech)


class ContentGenerator:
    """Generates blog content using LLM APIs.

    Example:
        >>> generator = ContentGenerator()
        >>> content = generator.generate(
        ...     topic="AI Tools for Developers",
        ...     keywords=["ai", "developer", "tools"],
        ...     content_type=ContentType.REVIEW,
        ... )
        >>> print(content.title)
    """

    # Default prompt templates (embedded for simplicity)
    DEFAULT_PROMPTS = {
        ContentType.REVIEW: {
            "ko": """
{topic}에 대한 블로그 글을 작성하세요.

타겟 키워드: {keywords}

=== 톤앤매너 ===
- 어조: 전문적이지만 초보자도 이해하기 쉬운 친절한 말투 (해요체)
- 가독성: 문단이 너무 길어지지 않게 나누고 (2-3문장), 중요 내용은 <strong>으로 강조
- 표(Table): 장단점 비교나 경쟁 기술 비교는 마크다운/HTML 표로 정리

=== 필수 규칙 ===
- 반드시 한국어로만 작성 (해요체) - 영어 문장 절대 금지!
- "Based on...", "I'll create...", "Here's..." 같은 영어 메타 코멘트 절대 금지!
- HTML 태그만 바로 시작 - 설명이나 인트로 없이 바로 콘텐츠 출력!
- 확실하지 않은 가격/구독/무료체험 정보는 생략! (잘못된 정보보다 없는 게 나음)
- 현재 연도(2026년) 사용 - 절대 2025년 이전 연도 사용 금지
- 미래 전망은 "2026년" 내에서만 - 2027년 이상 연도 언급 금지 (2026년 초이므로 2027 예측은 시기상조)
- 팩트만 나열하지 말고 "왜 중요한지", "어떻게 활용할지" 인사이트 제공
- 주식/투자 분석 절대 금지
- 모든 통계/수치에 출처 링크 필수!

=== 데이터 & 통계 규칙 (E-E-A-T 필수!) ===
다양하고 풍부한 데이터를 출처와 함께 제공하세요. 더 많은 데이터 = 더 높은 가치!

**필수 데이터 유형 (글당 최소 4가지 포함):**

1. **공식 통계 데이터**:
   - 통계청(kosis.kr), 고용노동부, 한국은행 데이터
   - 형식: "평균 연봉 4,500만원 <a href="https://kosis.kr/..." target="_blank" rel="noopener">(통계청 2024)</a>"

2. **시장/업계 데이터**:
   - 잡코리아, 사람인, 원티드 채용 동향
   - 업계 리포트, 설문조사 결과
   - 형식: "IT 개발자 채용 수요 전년 대비 23% 증가 <a href="[출처]" target="_blank" rel="noopener">(잡코리아 2024)</a>"

3. **비교 데이터**:
   - 가격/연봉/비용 비교표
   - 기능/성능 비교 매트릭스
   - 모든 비교표에 출처 각주 포함

4. **트렌드 데이터**:
   - 검색 트렌드 (네이버 데이터랩, 구글 트렌드)
   - 연도별 변화 추이
   - 형식: "검색량 전년 대비 45% 상승 <a href="[출처]" target="_blank" rel="noopener">(네이버 데이터랩)</a>"

5. **사용자/커뮤니티 데이터**:
   - 앱 다운로드 수, 사용자 리뷰 평점
   - 커뮤니티 회원 수, 활성 사용자
   - 형식: "네이버 카페 회원 15만명 <a href="[출처]" target="_blank" rel="noopener">(출처)</a>"

**데이터 시각화 (통계 카드):**
<div style="display:flex;flex-wrap:wrap;gap:12px;margin:20px auto;max-width:800px;">
<div style="flex:1;min-width:140px;background:#2d2d3a;padding:16px;border-radius:8px;text-align:center;">
<div style="font-size:1.8em;font-weight:bold;color:#a78bfa;">4,500만</div>
<div style="color:#94a3b8;font-size:0.85em;">평균 연봉</div>
<a href="https://kosis.kr" target="_blank" rel="noopener" style="color:#64b5f6;font-size:0.75em;">통계청 2024</a>
</div>
</div>

**출처 표기 원칙:**
- 모든 수치에 클릭 가능한 출처 링크 필수
- 허용 출처: 통계청, 정부기관, 공식 사이트, 언론사, 리서치 기관
- 출처 없는 경우: "업계 추정", "커뮤니티 의견" 등으로 명시 (최소화)
- "90%가 모르는", "대부분의 사람들이" 같은 검증 불가 표현 금지!

**데이터 체크리스트:**
□ 최소 1개 공식 통계 (통계청, 정부기관)
□ 최소 2개 업계/시장 데이터
□ 모든 비교표에 출처 명시
□ 트렌드/변화 데이터 포함

=== E-E-A-T 요소 (Google 품질 신호 - 필수!) ===
경험(Experience), 전문성(Expertise), 권위(Authoritativeness), 신뢰(Trust) 요소 포함:

**1. 작성 정보 (본문 상단에 추가):**
<p style="color:#94a3b8;font-size:0.85em;margin:8px auto;max-width:800px;">마지막 업데이트: 2026년 1월 | 읽는 시간: X분</p>

**2. 출처 섹션 (결론 전에 추가):**
<div style="margin:30px auto;padding:20px;background:#2d2d3a;border-radius:8px;max-width:800px;">
<h3 style="color:#a78bfa;margin-top:0;">📚 참고 자료</h3>
<ul style="color:#94a3b8;padding-left:20px;line-height:1.8;">
<li><a href="[URL]" target="_blank" rel="noopener" style="color:#64b5f6;">[출처명]</a> - [사용한 데이터 설명]</li>
</ul>
</div>

**3. 방법론 노트 (비교/분석 글에 추가):**
<div style="background:#1e3a5f;padding:16px;border-radius:8px;margin:20px auto;border-left:3px solid #3b82f6;max-width:800px;">
<strong style="color:#60a5fa;">📋 분석 방법</strong>
<p style="color:#94a3b8;margin:8px 0 0 0;font-size:0.9em;">
[분석 방법 간단 설명 - 예: "본 비교는 2024년 채용공고 3,000건 분석 및 공식 통계 자료를 기반으로 작성되었습니다."]
</p>
</div>

**E-E-A-T 체크리스트:**
□ 마지막 업데이트 날짜 포함
□ 모든 통계에 출처 링크
□ 참고 자료 섹션 포함
□ 분석 방법 명시 (비교글의 경우)

=== Yoast SEO 최적화 규칙 (필수!) ===
CRITICAL: 아래 규칙을 반드시 준수해야 Yoast SEO 점수가 올라갑니다!

1. **서두 키프레이즈 (첫 단락)**:
   - 첫 번째 문단에 반드시 토픽의 핵심 키워드를 자연스럽게 포함!
   - 예: 토픽이 "2026년 직종 연봉 비교"면 → "2026년 직종 연봉 비교, 어떤 직업이 가장 유망할까요?"로 시작

2. **키워드 밀도 (최소 5회 - 중요!)**:
   - 본문 전체에 핵심 키프레이즈를 최소 5회 이상 자연스럽게 반복
   - 서두(1회), 본문 섹션들(3회), 결론(1회)에 분산 배치
   - 예: "이번 연봉 비교에서...", "직종별 연봉 비교 결과...", "연봉 비교 시 고려할 점...", "연봉 비교를 정리하면...", "최종 연봉 비교 결론은..."

3. **H2 소제목에 키프레이즈 포함**:
   - 최소 1-2개의 H2 제목에 핵심 키워드 또는 동의어 포함
   - 예: "IT 직종 분석" → "2026 IT 직종 연봉 비교"
   - 예: "금융권 분석" → "금융권 직종별 연봉 총정리"

4. **내부 링크 (필수 1개 이상)**:
   - trendpulse.blog 내 관련 포스트로 연결
   - 취업 카테고리: <a href="https://trendpulse.blog/category/취업/">다른 취업 정보</a>
   - 또는 관련 주제 링크: "외항사 취업에 관심 있다면 <a href="https://trendpulse.blog/category/취업/">취업 가이드</a>도 참고하세요."

5. **외부 링크 (필수 1개 이상)**:
   - 신뢰할 수 있는 외부 사이트 링크 포함
   - 예: <a href="https://www.jobkorea.co.kr" target="_blank" rel="noopener">잡코리아</a>
   - 예: <a href="https://www.saramin.co.kr" target="_blank" rel="noopener">사람인</a>
   - 예: <a href="https://www.wanted.co.kr" target="_blank" rel="noopener">원티드</a>
   - 예: <a href="https://kosis.kr" target="_blank" rel="noopener">통계청</a>
   - 카테고리별 외부 링크:
     - 취업: 잡코리아, 사람인, 원티드, 인크루트
     - 테크: GitHub, Stack Overflow, 공식 문서
     - 건강: 대한의학회, 질병관리청
     - 리뷰: 제품 공식 사이트
     - 생산성: Notion, Obsidian 등 공식 사이트

=== 스타일 규칙 ===
- 짧은 문단 (2-3문장) - 가독성이 생명
- 표(table)를 적극 활용하여 비교/정리
- <strong>으로 핵심 문구 강조
- 모든 H2 섹션에: <!-- IMAGE: 설명 -->
- 총 단어 수: 1200-1800 단어

=== HTML 스타일 필수 규칙 (가로폭 800px 통일) ===

[코드 블록 스타일] - 반드시 아래 형식 사용:
<pre style="background-color:#1e1e1e;color:#d4d4d4;padding:16px;border-radius:8px;overflow-x:auto;font-family:monospace;font-size:14px;line-height:1.5;max-width:800px;margin:20px auto;">
2026-01-03 -15000 점심 회식 (이탈리안)
2026-01-03 +3000000 월급
</pre>

[표(Table) 스타일] - 모바일 반응형 필수! (가로 스크롤):
<div style="overflow-x: auto; margin: 0 auto 30px auto; max-width: 800px;">
<table style="width:100%;min-width:400px;border-collapse:separate;border-spacing:0;border-radius:12px;overflow:hidden;box-shadow:0 4px 15px rgba(0,0,0,0.2);">
<thead>
<tr style="background:#5046e5;">
<th style="padding:16px 20px;text-align:center;color:#fff;font-weight:600;font-size:0.95em;white-space:nowrap;">항목</th>
<th style="padding:16px 20px;text-align:center;color:#fff;font-weight:600;font-size:0.95em;white-space:nowrap;">설명</th>
</tr>
</thead>
<tbody>
<tr style="background:#2d2d3a;">
<td style="padding:14px 20px;text-align:center;color:#f0f0f0;border-bottom:1px solid #3d3d4a;">내용1</td>
<td style="padding:14px 20px;text-align:center;color:#f0f0f0;border-bottom:1px solid #3d3d4a;">내용2</td>
</tr>
<tr style="background:#252532;">
<td style="padding:14px 20px;text-align:center;color:#f0f0f0;">내용3</td>
<td style="padding:14px 20px;text-align:center;color:#f0f0f0;">내용4</td>
</tr>
</tbody>
</table>
</div>
중요: 모든 테이블은 반드시 <div style="overflow-x: auto;">로 감싸서 모바일에서 가로 스크롤 가능하게!
※ 헤더는 브랜드 컬러(#5046e5) + 흰 글씨
※ 바디는 다크 배경(#2d2d3a, #252532 교차) + 밝은 글씨(#f0f0f0)

[제품/도구 링크] - 다크테마 대응 (밝은 강조색):
- Notion → <a href="https://www.notion.so" target="_blank" rel="noopener" style="color:#64b5f6;font-weight:bold;text-decoration:underline;">Notion</a>
- Obsidian → <a href="https://obsidian.md" target="_blank" rel="noopener" style="color:#64b5f6;font-weight:bold;text-decoration:underline;">Obsidian</a>
- VS Code → <a href="https://code.visualstudio.com" target="_blank" rel="noopener" style="color:#64b5f6;font-weight:bold;text-decoration:underline;">VS Code</a>
- ChatGPT → <a href="https://chat.openai.com" target="_blank" rel="noopener" style="color:#64b5f6;font-weight:bold;text-decoration:underline;">ChatGPT</a>
※ 모든 도구/앱/서비스 링크는 color:#64b5f6 (밝은 파란색) + font-weight:bold 필수

[가독성 규칙] - 텍스트보다 시각화 우선:
- 긴 문장은 2-3줄로 나누고 개행 추가
- 가능하면 텍스트 대신 도식화/다이어그램 사용
- 모든 콘텐츠 블록 max-width:800px로 통일
- 문단 사이 margin: 20px 이상

[숫자 데이터 시각화 - 필수!] - 숫자가 있으면 반드시 시각화:
CRITICAL: 퍼센트(%), 점수, 비율, 순위 등 숫자 데이터는 텍스트 대신 시각적 바/차트로 표현!

1. 점수/평점 바 (예: "성능 9/10점"):
<div style="max-width:800px;margin:15px auto;">
<div style="display:flex;align-items:center;gap:12px;margin:8px 0;">
<span style="width:100px;color:#cbd5e1;">성능:</span>
<div style="flex:1;height:10px;background:#1a1a2e;border-radius:5px;overflow:hidden;">
<div style="width:90%;height:100%;background:linear-gradient(90deg,#5046e5,#a78bfa);"></div>
</div>
<span style="color:#a78bfa;font-weight:600;">9/10</span>
</div>
</div>

2. 퍼센트 비교 바 (예: "만족도 85%"):
<div style="max-width:800px;margin:15px auto;">
<div style="margin:12px 0;">
<div style="display:flex;justify-content:space-between;margin-bottom:6px;">
<span style="color:#cbd5e1;">A 제품</span>
<span style="color:#a78bfa;font-weight:600;">85%</span>
</div>
<div style="height:12px;background:#1a1a2e;border-radius:6px;overflow:hidden;">
<div style="width:85%;height:100%;background:linear-gradient(90deg,#5046e5,#a78bfa);border-radius:6px;"></div>
</div>
</div>
<div style="margin:12px 0;">
<div style="display:flex;justify-content:space-between;margin-bottom:6px;">
<span style="color:#cbd5e1;">B 제품</span>
<span style="color:#60a5fa;font-weight:600;">72%</span>
</div>
<div style="height:12px;background:#1a1a2e;border-radius:6px;overflow:hidden;">
<div style="width:72%;height:100%;background:linear-gradient(90deg,#3b82f6,#60a5fa);border-radius:6px;"></div>
</div>
</div>
</div>

3. 순위/TOP 리스트 시각화:
<div style="max-width:800px;margin:20px auto;">
<div style="display:flex;align-items:center;gap:15px;padding:16px;background:#2d2d3a;border-radius:10px;margin:10px 0;">
<div style="width:50px;height:50px;background:linear-gradient(135deg,#ffd700,#ffb800);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1.5em;font-weight:bold;color:#1a1a2e;">1</div>
<div style="flex:1;">
<strong style="color:#fff;font-size:1.1em;">1위 항목명</strong>
<p style="margin:5px 0 0 0;color:#a0a0a0;font-size:0.9em;">간단한 설명</p>
</div>
<span style="color:#ffd700;font-weight:bold;">⭐ 98점</span>
</div>
</div>

4. 비교 차트 (장단점 등):
<div style="max-width:800px;margin:20px auto;display:flex;gap:15px;flex-wrap:wrap;">
<div style="flex:1;min-width:250px;background:#1e3a5f;padding:16px;border-radius:8px;border-left:4px solid #3b82f6;">
<strong style="color:#60a5fa;">✓ 장점</strong>
<ul style="margin:8px 0 0 0;padding-left:16px;color:#e8e8e8;">
<li>장점 1</li>
<li>장점 2</li>
</ul>
</div>
<div style="flex:1;min-width:250px;background:#3a1e1e;padding:16px;border-radius:8px;border-left:4px solid #ef4444;">
<strong style="color:#f87171;">✗ 단점</strong>
<ul style="margin:8px 0 0 0;padding-left:16px;color:#e8e8e8;">
<li>단점 1</li>
<li>단점 2</li>
</ul>
</div>
</div>

※ 규칙:
- "성능이 좋다" → 점수 바로 시각화 (9/10)
- "85% 만족도" → 퍼센트 바로 시각화
- "A가 B보다 30% 빠르다" → 비교 바 2개로 시각화
- TOP 5 리스트 → 순위 카드로 시각화
- 장단점 → 장단점 박스로 시각화

[리스트 스타일] - 다크테마 + 트렌디 색상:
<ul style="max-width:800px;margin:20px auto;padding-left:25px;text-align:left;">
<li style="margin-bottom:10px;color:#cbd5e1;line-height:1.7;">항목 내용</li>
</ul>

[본문 텍스트 스타일] - 다크테마 + 소프트 블루틴트:
<p style="max-width:800px;margin:15px auto;text-align:left;line-height:1.8;color:#cbd5e1;">
본문 내용
</p>

[H2 제목 스타일] - 그라데이션 텍스트 (트렌디):
<h2 style="font-size:1.5em;margin:40px auto 20px auto;max-width:800px;background:linear-gradient(135deg,#a78bfa,#60a5fa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">섹션 제목</h2>

[strong 강조 스타일] - 밝은 보라색:
<strong style="color:#a78bfa;">강조 텍스트</strong>

[전체 정렬 규칙]:
- 모든 블록(p, ul, ol, table, pre, div)은 max-width:800px + margin:0 auto
- 블록 내부 텍스트는 text-align:left (제목, 요약 박스 제외)
- 항상 line-height:1.6~1.8 유지
- ※ 다크테마 색상:
  - 본문/리스트: #cbd5e1 (소프트 블루틴트)
  - H2 제목: 보라-블루 그라데이션
  - 강조(strong): #a78bfa (밝은 보라)
  - 박스 내부: 배경에 맞춰 #333

[도식화 박스 스타일] - 다크테마 대응:
<div style="max-width:800px;margin:25px auto;padding:20px;background:#2d2d3a;border-radius:12px;border-left:4px solid #5046e5;">
<p style="margin:0 0 10px 0;font-size:1.1em;font-weight:bold;color:#fff;">💬 핵심 메시지</p>
<p style="margin:0;color:#e0e0e0;line-height:1.8;">
첫 번째 포인트<br/>
두 번째 포인트<br/>
세 번째 포인트
</p>
</div>

예시 - 다음처럼 긴 텍스트:
❌ "완벽하게 시작하려고 하지 마세요. 오늘 한 줄만 적어도 성공이에요..."

이렇게 도식화:
✅
<div style="max-width:800px;margin:25px auto;padding:25px;background:#2d2d3a;border-radius:12px;text-align:center;box-shadow:0 4px 15px rgba(0,0,0,0.3);">
<p style="font-size:2em;margin:0 0 15px 0;">🎯</p>
<p style="font-size:1.2em;font-weight:bold;color:#fff;margin:0 0 10px 0;">완벽하게 시작하지 마세요</p>
<p style="color:#b0b0b0;margin:0;">오늘 딱 한 줄만 적어도 성공이에요</p>
<p style="margin-top:15px;padding:10px;background:#1e1e1e;border-radius:8px;font-family:monospace;color:#d4d4d4;">2026-01-08 -4500 커피</p>
<p style="color:#888;font-size:0.9em;margin-top:10px;">↑ 1억 모은 사람들의 첫 기록도 이거였어요</p>
</div>

=== 구조 패턴 (AI 탐지 방지를 위해 다양화!) ===
중요: 모든 글에 동일한 구조를 사용하지 마세요!
토픽 유형에 따라 아래 패턴 중 하나를 선택하세요.

**패턴 A - 비교 분석형** (X vs Y, 순위, 목록 토픽):
1. 업데이트 날짜 + 읽는 시간
2. 핵심 요약 박스 ("한눈에 보기" 또는 "핵심 비교")
3. 주요 데이터 카드 (통계 수치 3-4개)
4. 상세 비교표 (출처 포함)
5. 항목별 심층 분석 (5-6개 H2)
6. 참고 자료 섹션
7. 결론 + 추천

**패턴 B - 가이드/방법형** (하는 법, 시작하기, 준비 토픽):
1. 업데이트 날짜
2. 이 글에서 배울 내용 (불릿 포인트)
3. 왜 중요한지 (배경/문제)
4. 단계별 가이드 (5-7개 H2):
   - 준비 사항
   - 단계 1, 2, 3...
   - 주의할 점
   - 자주 하는 실수
5. 실제 사례/경험
6. FAQ
7. 다음 단계 제안

**패턴 C - 심층 분석형** (트렌드, 전망, 현황 토픽):
1. 업데이트 날짜 + 분석 방법론
2. 핵심 발견 요약 (불릿, 박스 아님)
3. 데이터 기반 분석 (6-7개 H2):
   - 현황 개요 (통계 카드)
   - 주요 트렌드 분석
   - 세부 항목별 분석
   - 비교 데이터
   - 전문가 의견/인용
4. 참고 자료 섹션
5. 결론 및 시사점

**패턴 D - 리뷰/후기형** (제품, 서비스 리뷰):
1. 업데이트 날짜
2. 한줄 평가 박스
3. 평가 항목별 점수 바
4. 상세 리뷰 (5-6개 H2):
   - 첫인상/시작 경험
   - 주요 기능 분석
   - 장점 (구체적 사례)
   - 단점 (솔직하게)
   - 가격 대비 가치
   - 추천 대상 / 비추천 대상
5. 대안 비교표
6. 최종 평가

**다양화 규칙:**
- "3줄 요약"을 매번 쓰지 말고: "핵심 포인트", "한눈에 보기", "빠른 요약" 등 변형
- 요약 박스 위치도 변형 (상단 또는 비교표 후)
- 콜아웃 박스 스타일 다양화 (팁, 주의, 정보 등)
- H2 제목 스타일 변형: 질문형, 서술형, 행동형

※ 중요: 콘텐츠에 H1 태그 절대 사용 금지! (WordPress가 제목을 H1으로 자동 렌더링함)
※ 본문은 H2부터 시작

=== 제목 최적화 (정보성 + 신뢰성 중심) ===
CRITICAL: 클릭베이트 대신 정보성과 신뢰성을 강조하세요!

**권장 요소:**

1. **정보성 워드** (1-2개 권장):
   권장: 총정리, 비교분석, 실제후기, 상세가이드, 핵심정리, 데이터분석, 현실적인
   → "2026 직종별 연봉 상세 비교분석" ✓ "실제 사용 후기와 데이터" ✓

2. **구체적 수치** (데이터 기반만):
   출처가 있는 숫자만 사용
   → "통계청 자료 기준", "2024 설문조사 결과" (출처 명시 필수)

3. **구체적 키워드** (전문 용어, 브랜드명):
   → 도구명, 직종명, 연도(2026), 지역명 등

4. **독자 혜택 명시**:
   → "...선택 가이드", "...비교표 포함", "...체크리스트"

**신뢰성 있는 제목 공식:**
- "[연도] [주제] [정보성워드]: [독자혜택]"
  → "2026 IT 직종 연봉 비교분석: 통계청 데이터 기반"
- "[주제] [정보성워드] + [데이터출처]"
  → "프리랜서 vs 정규직 현실 비교 (실제 세금 계산 포함)"
- "[주제]: [구체적내용] 총정리"
  → "재택근무 직종 가이드: 업종별 현황과 전망"

**피해야 할 제목 (클릭베이트):**
- 과도한 감정: "충격!", "경악!", "대박!" ❌
- 검증 불가 수치: "90%가 모르는", "99%가 실패하는" ❌
- 자극적 표현: "후회하기 전에", "놓치면 손해" ❌
- 매번 같은 패턴 반복 ❌

**체크리스트:**
□ 정보성 워드 포함? (비교분석, 가이드, 총정리 등)
□ 구체적 키워드? (직종명, 도구명 등)
□ 수치가 있다면 출처 있는가?
□ 35-45자 이내?

**길이**: 30-45자 권장

2. 3줄 요약 박스 (본문 최상단, H1 없이 바로 시작) - What/How/Benefit 공식:
<div style="background-color:#e8f4fd;padding:20px;border-left:4px solid #0066cc;margin:20px auto;border-radius:4px;max-width:800px;">
<p style="margin:0 0 10px 0;font-weight:bold;color:#333333;font-size:1.1em;text-align:center;">⚡ 바쁜 분들을 위한 3줄 요약</p>
<ol style="margin:0;padding-left:20px;color:#333333;">
<li style="margin-bottom:8px;color:#333333;"><strong>What/Why:</strong> 핵심 주장 또는 왜 중요한지</li>
<li style="margin-bottom:8px;color:#333333;"><strong>How:</strong> 구체적인 방법 또는 핵심 포인트</li>
<li style="margin-bottom:8px;color:#333333;"><strong>Benefit:</strong> 독자가 얻는 이득 또는 결론</li>
</ol>
</div>

※ 3줄 요약 예시:
- What: "10년간 텍스트 가계부를 쓴 개발자들이 앱보다 낫다고 입증했다"
- How: "메모장에 날짜, 금액, 내용 3가지만 적으면 된다"
- Benefit: "돈 관리도 잘되고 데이터는 평생 내 것이다"

3. 도입부: 왜 지금 이게 중요한지

4. 본문 섹션 (동적 생성 - 토픽에 맞게 5-7개 선택):
※ 아래 섹션 중 토픽에 적합한 것만 선택하여 작성 (모두 필수 아님)
※ 각 섹션은 <!-- IMAGE: 설명 --> + 2-3개 짧은 문단 + 도식화/표

[선택 가능한 섹션 유형]
□ 핵심 개념 설명 - 이게 뭔지, 왜 중요한지
□ 실제 활용 사례 - 코드/예시 전에 안심 문구 필수: "복잡해 보이나요? 원리는 간단해요."
□ 장단점 비교 - 표로 정리, 현대적 관점 (도파민 없는 쾌적함 등)
□ 추천 도구 비교 - 표로 정리 (도구명에 공식 링크 필수)
□ 시작 방법 - 구체적 단계
□ AI 활용법 - ChatGPT 프롬프트 예시 포함
□ 주의사항/실수 피하기
□ 고급 팁

※ "시작 가이드"와 "액션플랜"은 중복되므로 하나만 선택
※ 토픽과 무관한 섹션은 과감히 제외

5. 핵심 인사이트 박스:
<div style="background-color:#fff8e1;padding:20px;border-left:4px solid #ff9800;margin:20px auto;border-radius:4px;max-width:800px;">
<p style="margin:0 0 10px 0;font-weight:bold;color:#333333;font-size:1.1em;text-align:center;">💡 핵심 인사이트</p>
<p style="margin:0;color:#333333;">여기에 독자가 다른 곳에서 얻기 어려운 인사이트 작성</p>
</div>

6. FAQ 섹션 (H2): 3-4개 실용적인 질문과 답변

7. 결론 + 액션플랜 (도식화 필수):
액션플랜은 반드시 아래 플로우차트 스타일로 작성 (불투명 배경 + 높은 대비):
<div style="max-width:800px;margin:30px auto;">
<div style="background:#5046e5;color:#ffffff;padding:24px;border-radius:12px;text-align:center;margin-bottom:15px;box-shadow:0 4px 15px rgba(80,70,229,0.4);">
<strong style="font-size:1.2em;display:block;margin-bottom:8px;">🚀 Step 1</strong>
<span style="font-size:1em;">첫 번째 행동 (예: 메모장 열기)</span>
</div>
<div style="text-align:center;font-size:32px;color:#5046e5;margin:10px 0;">↓</div>
<div style="background:#e91e63;color:#ffffff;padding:24px;border-radius:12px;text-align:center;margin-bottom:15px;box-shadow:0 4px 15px rgba(233,30,99,0.4);">
<strong style="font-size:1.2em;display:block;margin-bottom:8px;">📝 Step 2</strong>
<span style="font-size:1em;">두 번째 행동 (예: 오늘 지출 1개 기록)</span>
</div>
<div style="text-align:center;font-size:32px;color:#e91e63;margin:10px 0;">↓</div>
<div style="background:#00bcd4;color:#ffffff;padding:24px;border-radius:12px;text-align:center;box-shadow:0 4px 15px rgba(0,188,212,0.4);">
<strong style="font-size:1.2em;display:block;margin-bottom:8px;">✅ Step 3</strong>
<span style="font-size:1em;">세 번째 행동 (예: 일주일 후 패턴 확인)</span>
</div>
</div>
※ 반드시 3-4단계 플로우차트 형태로 시각화할 것
※ 각 박스는 불투명 단색 배경 + 그림자 효과로 가독성 확보
※ 모든 박스/표/코드블록은 max-width:800px 통일

이미지 플레이스홀더 (영어):
<!-- IMAGE: modern workspace with laptop -->
<!-- IMAGE: person working productively -->

출력: HTML만, 마크다운 없이, 코멘트 없이.
""",
            "en": """
Write an expert-level, PURCHASE-DECISION-FOCUSED blog post about: {topic}

Target keywords: {keywords}

=== BYTEPULSE.IO MISSION ===
Help developers and startup founders make BUYING DECISIONS.
NOT just information - guide them to ACTION (signup, purchase, migrate).
Transform this from "informative" to "SELLING" content.

=== TITLE OPTIMIZATION (SEO Score 60+ Required) ===
GOAL: Headline Analyzer score 60+, informative yet engaging, NO clickbait spam.

**WORD BALANCE FOR HIGH SCORES:**

1. **POWER WORDS** (Use 1 - NOT spammy ones):
   ALLOWED: Complete, Essential, Proven, Comprehensive, Critical, Definitive, Practical
   BANNED: Shocking, Incredible, Mind-Blowing, Ultimate, Secret, Unbelievable
   → "Complete 2026 Comparison" ✓ "Essential Migration Guide" ✓

2. **UNCOMMON/TECHNICAL WORDS** (Use 2-3 - boosts score):
   Use specific technical terms developers search for
   → Benchmark, Migration, Deployment, Latency, Performance, Pricing, Integration
   → Tool names count as uncommon: Cursor, Copilot, Vercel, TSMC, etc.

3. **EMOTIONAL/ACTION WORDS** (Use 1 - subtle ones):
   ALLOWED: Critical, Key, Important, Real, Tested, Compared, Analyzed
   BANNED: Mistake, Fear, Warning, Hate, Painful, Embarrassing
   → "Critical Differences" ✓ "Key Performance Metrics" ✓

4. **NUMBERS** (Include when factual):
   → "7 Key Differences", "2026 Benchmark", "30-Day Testing Results"

**HIGH-SCORING TITLE FORMULAS (60+ verified):**
- "[Tool A] vs [Tool B] 2026: Complete [Aspect] Comparison"
  → "Cursor vs Copilot 2026: Complete Performance Comparison" (58 chars, ~65 score)
- "[Tool A] vs [Tool B]: [Number] Key Differences [Context]"
  → "Apple vs Nvidia: 5 Critical TSMC Capacity Differences" (52 chars, ~68 score)
- "[Year] [Topic]: Comprehensive [Benefit] with [Data Type]"
  → "2026 Vietnam Ad Regulations: Comprehensive Compliance Guide" (58 chars, ~62 score)
- "[Tool] Review: [Number]-Day Real-World [Aspect] Analysis"
  → "Claude Code Review: 30-Day Real-World Performance Analysis" (57 chars, ~64 score)

**TITLE CHECKLIST (aim for all):**
□ 1 Power word (Complete, Essential, Comprehensive, Critical)
□ 2-3 Uncommon/technical words (tool names, jargon)
□ 1 Emotional/action word (Key, Critical, Real, Tested)
□ Year or number included
□ 50-60 characters (optimal range)

**BANNED PATTERNS (Google flags as AI spam):**
- "Shocking", "Incredible", "Mind-Blowing" ❌
- "X Mistakes That...", "The Truth About..." ❌
- "You Won't Believe", "What No One Tells You" ❌
- Same formula repeated across posts ❌

**LENGTH**: 50-60 characters REQUIRED (not shorter!)

=== CONTENT TYPE PRIORITY (50%+ should be VS/Comparison) ===
1. **VS Comparisons** (HIGHEST PRIORITY): "Cursor vs GitHub Copilot", "Linear vs Jira"
   - Developers searching "X vs Y" are READY TO BUY
   - Include pricing tables, feature matrices, verdict

2. **Migration Guides**: "How to migrate from Jira to Linear"
   - Low competition, high intent audience
   - Include LEAD GEN hook: "Download my migration checklist (free PDF)"

3. **Tool Reviews**: Deep dive with affiliate links
   - Focus on "Best for X" recommendations

=== MOBILE-FIRST FORMATTING (Critical!) ===
- MAX 2-3 sentences per paragraph (mobile screens are narrow!)
- Use BOLD liberally: **Linear wins on speed**, **This is the $2,000 mistake**
- Every key insight should be in a callout box (see templates below)
- Whitespace is your friend - break up text walls

=== CTA BUTTON (Only ONE at article END!) ===
IMPORTANT: Only ONE CTA button in the ENTIRE article - place at the very END (Final Verdict section).
DO NOT put CTA buttons in Pricing, Features, or middle sections.

<div style="text-align: center; margin: 30px 0;"><a href="https://vercel.com" style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 16px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 1.1em; box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);">🚀 Start Free Today</a></div>

CRITICAL: NO line breaks inside <a> tags! Button HTML must be on single line.

=== MONETIZATION HOOKS (Required) ===
- Button CTAs with urgency: "Start Free (No Credit Card)"
- Mention FREE TIER limitations: "Free plan limits you to 10 users"
- Recommend tools with RECURRING COMMISSION (Webflow, Semrush, Notion, Linear)

=== DATA & STATISTICS (CRITICAL for E-E-A-T!) ===
Include RICH, DIVERSE data with VERIFIED SOURCES. More data = more value!

**REQUIRED DATA TYPES (Include at least 4 types per article):**

1. **Official Pricing Data** (Always include):
   - Link to official pricing page
   - Format: "$X/month <a href="https://tool.com/pricing" target="_blank" rel="noopener">(source)</a>"

2. **Performance Benchmarks** (When comparing tools):
   - GitHub stars, npm downloads, Docker pulls
   - Response times from official docs or reputable benchmarks
   - Format: "1.2s average response time <a href="[source]" target="_blank" rel="noopener">(source: Official Docs)</a>"

3. **Market/Usage Statistics**:
   - Stack Overflow Developer Survey data
   - State of JS/CSS/DevOps survey results
   - GitHub Octoverse reports
   - Gartner/Forrester reports (if available)
   - Format: "Used by 45% of developers <a href="https://survey.stackoverflow.co/2024" target="_blank" rel="noopener">(Stack Overflow 2024)</a>"

4. **Community Metrics**:
   - GitHub: stars, forks, contributors, issues
   - Discord/Slack community size
   - Reddit subscriber counts
   - Format: "47k GitHub stars, 2.3k contributors <a href="https://github.com/org/repo" target="_blank" rel="noopener">(GitHub)</a>"

5. **Version/Release Data**:
   - Current version, release date
   - Major version history
   - Link to changelog

6. **Comparison Tables with Sources**:
   Every comparison table should have a "Source" column or footnotes

**DATA PRESENTATION TEMPLATES:**

Stats Card WITH verified external source (GitHub, official site):
<div style="display: flex; flex-wrap: wrap; gap: 12px; margin: 20px 0;">
<div style="flex: 1; min-width: 140px; background: #1a1a2e; padding: 16px; border-radius: 8px; text-align: center;">
<div style="font-size: 1.8em; font-weight: bold; color: #00d9ff;">47k+</div>
<div style="color: #94a3b8; font-size: 0.85em;">GitHub Stars</div>
<a href="https://github.com/getcursor/cursor" style="color: #3b82f6; font-size: 0.75em;">GitHub</a>
</div>
</div>

Stats Card for OWN TESTING data (Link to benchmark section with anchor!):
<div style="flex: 1; min-width: 140px; background: #1a1a2e; padding: 16px; border-radius: 8px; text-align: center;">
<div style="font-size: 1.8em; font-weight: bold; color: #00d9ff;">0.8s</div>
<div style="color: #94a3b8; font-size: 0.85em;">Response Time</div>
<a href="#benchmark-methodology" style="color: #3b82f6; font-size: 0.75em;">our benchmark ↓</a>
</div>

⚠️ IMPORTANT: When using "our testing/benchmark" data, you MUST:
1. Link to #benchmark-methodology anchor (NOT external URL)
2. Include the BENCHMARK METHODOLOGY section at the end of the article (see below)

Source Citation (use inline):
- External verified: <a href="https://github.com/..." style="color: #3b82f6;">GitHub</a>
- Own testing data: <a href="#benchmark-methodology" style="color: #3b82f6;">our benchmark ↓</a>

**SOURCE REQUIREMENTS (CRITICAL - NO FAKE URLS!):**
⚠️ NEVER generate fake or hallucinated URLs! Only use these verified URL patterns:

**ALLOWED SOURCE LINKS (use ONLY these exact patterns):**
- Internal anchor: #benchmark-methodology (for your own testing data - MUST use this!)
- Official product homepages: https://cursor.sh, https://linear.app, https://github.com/features/copilot
- GitHub repos: https://github.com/[org]/[repo] (ONLY if repo actually exists)
- Official pricing pages: https://[product].com/pricing
- Stack Overflow Survey: https://survey.stackoverflow.co/2024
- npm packages: https://www.npmjs.com/package/[package-name]

**FOR "OUR TESTING" DATA - ALWAYS USE ANCHOR LINK:**
When you write stats like "0.8s response time", you MUST add this EXACT anchor link:
<a href="#benchmark-methodology" style="color: #3b82f6; font-size: 0.85em;">our benchmark ↓</a>

Example - CORRECT format for stats card:
<div style="font-size: 1.8em; color: #00d9ff;">0.8s</div>
<div style="color: #94a3b8;">Response Time</div>
<a href="#benchmark-methodology" style="color: #3b82f6; font-size: 0.75em;">our benchmark ↓</a>

❌ WRONG: <span>our benchmark ↓</span> (this is NOT clickable!)
✅ RIGHT: <a href="#benchmark-methodology">our benchmark ↓</a> (this IS clickable!)

**BANNED - DO NOT USE:**
- ❌ Specific news article URLs (Tom's Hardware, TechCrunch articles) - these are often hallucinated
- ❌ Deep links to specific blog posts or articles
- ❌ Any URL you're not 100% certain exists

**FOR NEWS/REPORT DATA - Use text citation instead:**
- ✅ "According to Tom's Hardware reports (January 2026)"
- ✅ "Per industry analysts"
- ✅ "Based on TSMC investor briefings"
- ❌ DO NOT link to specific article URLs

**FOR YOUR OWN TESTING DATA - USE ANCHOR LINKS + METHODOLOGY SECTION:**
When you claim data from "our testing", you MUST include a Benchmark Methodology section.

Stats reference format:
- ✅ "0.8s response time <a href='#benchmark-methodology'>our benchmark ↓</a>"

**DATA RICHNESS CHECKLIST:**
□ At least 1 pricing comparison table (link to official pricing pages only)
□ At least 3 performance/benchmark metrics (from your testing or official docs)
□ GitHub/npm stats with direct links to repo/package pages
□ News citations as TEXT only (no fake article URLs)

=== CONTENT QUALITY (Developers detect AI spam!) ===
- Real pros/cons - be HONEST about limitations
- Personal experience tone: "After using Linear for 6 months, I found..."
- Avoid generic fluff - every sentence must add value
- Every claim backed by data or clearly marked as opinion

=== STRICT RULES ===
- Write ONLY in English for US/UK/Global audience
- Use CURRENT YEAR (2026) - NEVER 2025 or older
- Be technically accurate - readers are EXPERTS

=== E-E-A-T ELEMENTS (MANDATORY - Content will be REJECTED without these!) ===
CRITICAL: You MUST include ALL of these elements. Missing ANY = content failure!

**1. AUTHOR + DATE HEADER (MANDATORY - Place IMMEDIATELY after H1):**
<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 16px; margin: 16px 0; padding: 16px; background: #1a1a2e; border-radius: 8px;">
<div style="display: flex; align-items: center; gap: 10px;">
<div style="width: 44px; height: 44px; background: linear-gradient(135deg, #3b82f6, #00d9ff); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; color: white; font-size: 1.1em;">BP</div>
<div>
<div style="color: #e8e8e8; font-weight: 600;">Bytepulse Engineering Team</div>
<div style="color: #94a3b8; font-size: 0.85em;">5+ years testing developer tools in production</div>
</div>
</div>
<div style="color: #64748b; font-size: 0.85em; margin-left: auto;">
<span>📅 Updated: January 22, 2026</span> · <span>⏱️ 8 min read</span>
</div>
</div>

**2. METHODOLOGY BOX (MANDATORY - Place after TL;DR):**
<div style="background: linear-gradient(135deg, #16213e 0%, #1a1a2e 100%); padding: 20px; border-radius: 12px; margin: 24px 0; border-left: 4px solid #3b82f6;">
<h4 style="color: #00d9ff; margin: 0 0 12px 0; font-size: 1em;">📋 How We Tested</h4>
<ul style="color: #94a3b8; margin: 0; padding-left: 20px; line-height: 1.8; font-size: 0.9em;">
<li><strong>Duration:</strong> 30+ days of real-world usage</li>
<li><strong>Environment:</strong> Production codebases (React, Node.js, Python)</li>
<li><strong>Metrics:</strong> Response time, accuracy, developer productivity</li>
<li><strong>Team:</strong> 3 senior developers with 5+ years experience</li>
</ul>
</div>

**3. INLINE SOURCE CITATIONS (NO FAKE URLS!):**
For statistics, use TEXT citations - NOT fake article URLs:

✅ GOOD (text citation): "Response time averaged 0.8 seconds <span style="color: #94a3b8; font-size: 0.85em;">(per official Cursor documentation)</span>"
✅ GOOD (verified link): "47k GitHub stars <a href="https://github.com/getcursor/cursor" target="_blank" rel="noopener" style="color: #3b82f6; font-size: 0.85em;">(GitHub)</a>"
✅ GOOD (own testing): "0.8s response time <span style="color: #94a3b8; font-size: 0.85em;">(our benchmark testing)</span>"

❌ BAD: Fake article URLs like "https://www.tomshardware.com/tech-industry/..." - NEVER DO THIS!

**4. SOURCES SECTION (MANDATORY - Only VERIFIED links!):**
<div style="margin: 32px 0; padding: 24px; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border-radius: 12px;">
<h3 style="color: #00d9ff; margin: 0 0 16px 0; font-size: 1.1em;">📚 Sources & References</h3>
<ul style="color: #94a3b8; padding-left: 20px; line-height: 2; margin: 0;">
<li><a href="https://[product].com" target="_blank" rel="noopener" style="color: #3b82f6;">[Tool] Official Website</a> - Pricing and features</li>
<li><a href="https://github.com/[org]/[repo]" target="_blank" rel="noopener" style="color: #3b82f6;">GitHub Repository</a> - Open source code and stats</li>
<li><span style="color: #e8e8e8;">Industry Reports</span> - Referenced throughout article (no direct links to avoid broken URLs)</li>
<li><span style="color: #e8e8e8;">Our Testing Data</span> - 30-day production benchmarks by Bytepulse team</li>
</ul>
<p style="color: #64748b; font-size: 0.8em; margin: 16px 0 0 0; font-style: italic;">
Note: We only link to official product pages and verified GitHub repos. News citations are text-only to ensure accuracy.
</p>
</div>

**5. EXPERIENCE STATEMENTS (MANDATORY - Include 3+ throughout content):**
Use first-person experience phrases naturally in the content:
- "In our 30-day testing period, we found..."
- "After migrating 3 production projects, the results showed..."
- "Our team's experience with [tool] revealed..."
- "Based on our benchmarks across 50k+ lines of code..."
- "We measured a [X]% improvement when..."

**E-E-A-T VALIDATION (ALL must be present):**
✓ Author header with credentials IMMEDIATELY after H1
✓ Methodology box after TL;DR
✓ Every statistic has inline source link
✓ Sources section before conclusion (minimum 4 sources)
✓ At least 3 first-person experience statements
✓ Specific numbers with context (not vague claims)

=== YOAST SEO OPTIMIZATION (CRITICAL!) ===
You MUST follow these rules to achieve high Yoast SEO scores:

1. **Keyphrase in Introduction (First Paragraph)**:
   - Include the main topic/keyphrase naturally in the FIRST paragraph!
   - Example: If topic is "Cursor vs Copilot", start with: "Cursor vs Copilot - which AI coding assistant wins in 2026?"

2. **Keyphrase Density (Minimum 5 times - CRITICAL!)**:
   - Repeat the core keyphrase at least 5 times throughout the content
   - Distribute across: introduction (1), body sections (3), conclusion (1)
   - Example: "In this comparison...", "Our testing shows...", "When comparing...", "The comparison reveals...", "Final verdict on this comparison..."

3. **Keyphrase in H2 Subheadings**:
   - Include keyphrase or synonyms in at least 1-2 H2 headings
   - Example: "Pricing Analysis" → "Cursor vs Copilot Pricing Comparison"
   - Example: "Features" → "Key Features: Cursor vs Copilot 2026"

4. **Internal Links (Required - at least 1)**:
   - Link to other bytepulse.io posts
   - Example: <a href="https://bytepulse.io/category/tools/">More developer tool reviews</a>
   - Or category link: <a href="https://bytepulse.io/category/comparison/">See more comparisons</a>

5. **External Links (Required - at least 1)**:
   - Link to authoritative external sources
   - Examples:
     - <a href="https://github.com" target="_blank" rel="noopener">GitHub</a>
     - <a href="https://stackoverflow.com" target="_blank" rel="noopener">Stack Overflow</a>
     - <a href="https://docs.cursor.sh" target="_blank" rel="noopener">Official Cursor Docs</a>
     - <a href="https://copilot.github.com" target="_blank" rel="noopener">GitHub Copilot</a>
   - Always include official product documentation links when reviewing tools
- No AI-generated smell - write like a senior developer

=== VISUAL-FIRST STYLE (CRITICAL! - Diagrams over Text) ===
PRIORITY: EVERY H2 SECTION MUST START WITH A VISUAL ELEMENT!

NO stock images - use TABLES, CHARTS, SCORE BARS instead.
Each H2 section structure:
1. H2 title
2. IMMEDIATELY show visual element (table/chart/score bar)
3. Then 1-2 short paragraphs explaining the visual
4. Pro tip or callout box

For each section, ask: "Can I show this instead of writing it?"
- Pricing → Comparison table FIRST (not paragraphs)
- Features → Feature matrix with ✓/✗ symbols FIRST
- Scores → Visual score bars FIRST (see template below)
- Pros/Cons → Side-by-side boxes FIRST
- Workflow → Step diagrams with arrows FIRST
- Comparison → Table or chart FIRST

REQUIRED VISUAL ELEMENTS (use these generously):
1. Score/Rating visualization (instead of "Tool A scores 9/10"):
<div style="display: flex; align-items: center; gap: 12px; margin: 8px 0;">
  <span style="width: 100px; color: #e8e8e8;">Speed:</span>
  <div style="flex: 1; height: 8px; background: #1a1a2e; border-radius: 4px; overflow: hidden;">
    <div style="width: 90%; height: 100%; background: linear-gradient(90deg, #3b82f6, #00d9ff);"></div>
  </div>
  <span style="color: #00d9ff; font-weight: 600;">9/10</span>
</div>

2. Pros/Cons boxes (stacked vertically - NO grid, grid breaks on mobile):
<div style="background: #1e3a5f; padding: 16px; border-radius: 8px; border-left: 4px solid #3b82f6; margin: 16px 0;">
  <strong style="color: #00d9ff;">✓ Pros</strong>
  <ul style="margin: 8px 0 0 0; padding-left: 16px; color: #e8e8e8;">
    <li>Pro point 1</li>
    <li>Pro point 2</li>
  </ul>
</div>
<div style="background: #1a1a2e; padding: 16px; border-radius: 8px; border-left: 4px solid #64748b; margin: 16px 0;">
  <strong style="color: #94a3b8;">✗ Cons</strong>
  <ul style="margin: 8px 0 0 0; padding-left: 16px; color: #94a3b8;">
    <li>Con point 1</li>
    <li>Con point 2</li>
  </ul>
</div>

IMPORTANT: Do NOT use CSS grid layouts (display: grid). They break on WordPress. Use stacked divs instead.

=== YOAST SEO OPTIMIZATION (CRITICAL!) ===
1. **Section Length**: MAX 300 WORDS per H2 section! If longer, add H3 subheadings.
2. **Keyphrase in H2/H3**: Include main keyphrase (e.g., "Vercel vs Netlify") or synonyms in at least 30% of subheadings.
3. **Internal Links**: Add 2-3 internal links to REAL categories:
   - <a href="/category/ai-tools/">AI Tools</a>
   - <a href="/category/dev-productivity/">Dev Productivity</a>
   - <a href="/category/saas-reviews/">SaaS Reviews</a>
   Example: "Want more comparisons? Check out our <a href=\"/category/dev-productivity/\">Dev Productivity</a> guides."
4. **Meta Description**: MUST include keyphrase AND be 150-160 characters.
5. **SEO Title**: Keep under 60 characters (shorter is better for mobile).

GENERAL RULES:
- START with TL;DR summary box FIRST (before any other content)
- Use VISUAL elements over text: comparison charts, score badges, diagrams
- SHORT paragraphs (2-3 sentences MAX, then visual element)
- MAX 300 words per H2 section (add H3 if longer!)
- Word count: 2000-3000 words (comprehensive)

=== COLOR PALETTE (MUST USE ONLY THESE - Consistent Blue/Cyan Theme) ===
- Primary: #3b82f6 (blue)
- Accent: #00d9ff (cyan)
- Text: #e8e8e8 (light gray)
- Muted: #94a3b8 (gray)
- Background: #1a1a2e, #16213e (dark blue)
- DO NOT use green (#4ade80), pink (#f472b6), orange (#f59e0b) for text
- Winner indicators: use ✓ text or blue badges only

=== REQUIRED HTML COMPONENTS ===

1. TL;DR SUMMARY BOX (MUST be FIRST after H1):
<div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border-left: 4px solid #3b82f6; border-radius: 12px; padding: 24px; margin: 24px 0; color: #e8e8e8;">
  <h3 style="color: #00d9ff; margin-top: 0; font-size: 1.3em;">⚡ TL;DR - Quick Verdict</h3>
  <ul style="margin: 0; padding-left: 20px; line-height: 1.8;">
    <li><strong style="color: #00d9ff;">Tool A</strong>: Best for [use case]. [One-line verdict]</li>
    <li><strong style="color: #00d9ff;">Tool B</strong>: Best for [use case]. [One-line verdict]</li>
  </ul>
  <p style="margin-top: 16px; padding-top: 16px; border-top: 1px solid #334155; color: #94a3b8;">
    <strong>My Pick:</strong> [Winner] for most teams. <a href="#verdict" style="color: #00d9ff;">Skip to verdict →</a>
  </p>
</div>

2. COMPARISON TABLE (MUST wrap in scrollable div for mobile!):
<div style="overflow-x: auto; margin: 24px 0;">
<table style="width: 100%; min-width: 500px; border-collapse: collapse; font-size: 0.95em;">
  <thead>
    <tr style="background: #1e3a5f;">
      <th style="padding: 12px; color: #00d9ff; text-align: left; white-space: nowrap;">Feature</th>
      <th style="padding: 12px; color: #00d9ff; text-align: center; white-space: nowrap;">Tool A</th>
      <th style="padding: 12px; color: #00d9ff; text-align: center; white-space: nowrap;">Tool B</th>
      <th style="padding: 12px; color: #00d9ff; text-align: center; white-space: nowrap;">Winner</th>
    </tr>
  </thead>
  <tbody>
    <tr style="background: #1a1a2e;">
      <td style="padding: 10px; border-bottom: 1px solid #333; color: #e8e8e8;">Price</td>
      <td style="padding: 10px; border-bottom: 1px solid #333; text-align: center; color: #e8e8e8;">$X/mo</td>
      <td style="padding: 10px; border-bottom: 1px solid #333; text-align: center; color: #e8e8e8;">$Y/mo</td>
      <td style="padding: 10px; border-bottom: 1px solid #333; text-align: center; color: #00d9ff;">Tool B ✓</td>
    </tr>
  </tbody>
</table>
</div>
CRITICAL: ALL tables MUST be wrapped in <div style="overflow-x: auto;"> for mobile scroll!

3. WINNER INDICATOR (simple, not colorful badges):
Use ✓ symbol next to winner, or: <span style="color: #00d9ff; font-weight: 600;">✓ Winner</span>

4. CALLOUT BOXES (tips/warnings - blue theme only):
<div style="background: #1e3a5f; border-radius: 8px; padding: 16px; margin: 16px 0; border-left: 4px solid #3b82f6;">
  <strong style="color: #00d9ff;">💡 Pro Tip:</strong>
  <span style="color: #e8e8e8;">[tip content]</span>
</div>

5. CTA BUTTONS (use REAL product URLs, blue theme):
IMPORTANT: Only ONE CTA button in the ENTIRE article - at the very END (Final Verdict/Conclusion section).
DO NOT put CTA buttons in Pricing, Features, or other middle sections.
CRITICAL: NO line breaks inside <a> tags! Button text must be on single line.

<div style="text-align: center; margin: 32px 0;"><a href="https://linear.app" target="_blank" rel="noopener" style="display: inline-block; background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); color: white; padding: 16px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 1.1em;">Try Linear Free →</a></div>

For linking to other tools, use inline text links (NOT buttons):
<p style="color: #94a3b8;">Also check out <a href="https://www.atlassian.com/software/jira" style="color: #00d9ff;">Jira</a> or <a href="https://asana.com" style="color: #00d9ff;">Asana</a>.</p>

=== COMMON PRODUCT URLS (Use these exact URLs) ===
- Linear: https://linear.app
- Jira: https://www.atlassian.com/software/jira
- Asana: https://asana.com
- Notion: https://www.notion.so
- Obsidian: https://obsidian.md
- Cursor: https://cursor.sh
- GitHub Copilot: https://github.com/features/copilot
- VS Code: https://code.visualstudio.com
- Vim/Neovim: https://neovim.io
- Figma: https://www.figma.com
- Slack: https://slack.com
- Discord: https://discord.com
- Vercel: https://vercel.com
- Netlify: https://www.netlify.com
- Supabase: https://supabase.com
- Firebase: https://firebase.google.com
- AWS: https://aws.amazon.com
- Docker: https://www.docker.com
- Linux: https://www.linux.org
- Windows: https://www.microsoft.com/windows

=== STRUCTURE PATTERNS (VARY to avoid AI detection!) ===
IMPORTANT: Do NOT use the same structure for every article!
Choose ONE pattern based on topic type. Vary your choice across articles.

**PATTERN A - Comparison Focus** (for "X vs Y" topics):
1. H1: Informative title with year
2. Key Stats Overview (GitHub stars, pricing snapshot)
3. TL;DR Summary Box
4. Head-to-Head Comparison Table
5. Deep Dive Sections (5-6 H2):
   - Pricing Analysis (with source links)
   - Performance Benchmarks (with data)
   - Feature Comparison
   - Best Use Cases
6. Data Summary Table
7. Final Verdict (id="verdict")
8. CTA button

**PATTERN B - Problem-Solution** (for guides, tutorials):
1. H1: Clear, descriptive title
2. The Problem (why this matters)
3. Quick Answer Box (not TL;DR - different format)
4. Solution Deep Dive (5-6 H2):
   - Understanding the Basics
   - Step-by-Step Implementation
   - Common Pitfalls (with examples)
   - Advanced Tips
   - Performance Considerations
5. Results/Outcomes (with metrics)
6. FAQ Section
7. Next Steps CTA

**PATTERN C - In-Depth Review** (for single tool reviews):
1. H1: "[Tool] Review: [Timeframe] of Testing"
2. Author Context (brief experience background)
3. Quick Verdict Box
4. What I Tested (methodology)
5. Deep Dive Sections (6-7 H2):
   - Getting Started Experience
   - Core Features Analysis
   - Performance (with benchmark data)
   - Pricing Value Analysis
   - Who Should Use This
   - Who Should NOT Use This
6. Alternatives Comparison Table
7. Final Rating with Breakdown
8. CTA button

**PATTERN D - Data-Driven Analysis** (for trends, market analysis):
1. H1: "[Year] [Topic]: Data-Driven Analysis"
2. Key Findings Summary (bullet points, not box)
3. Methodology Note
4. Analysis Sections (5-6 H2):
   - Market Overview (with charts/stats)
   - Trend Analysis (with historical data)
   - Tool/Option Breakdown
   - Cost Analysis
   - Predictions & Recommendations
5. Data Sources Section
6. Conclusion with Action Items

**VARIATION RULES:**
- Never use "TL;DR" in every article - vary: "Quick Verdict", "Key Takeaways", "At a Glance"
- Alternate section ordering across articles
- Use different callout box styles (tip boxes, warning boxes, info boxes)
- Vary heading styles: questions, statements, action phrases

=== FAQ SECTION (MANDATORY - Content will be REJECTED without this!) ===
You MUST include a FAQ section with EXACTLY this structure:

<h2 style="color: #00d9ff; border-bottom: 2px solid #3b82f6; padding-bottom: 8px;">FAQ</h2>

Include 4-5 REAL questions developers would ask. Use this exact HTML format:

<div style="margin: 20px 0;">
<details style="background: #1a1a2e; border-radius: 8px; margin: 12px 0; border: 1px solid #3b82f6;">
<summary style="padding: 16px; cursor: pointer; font-weight: 600; color: #e8e8e8;">Q: [Specific, practical question]?</summary>
<div style="padding: 0 16px 16px 16px; color: #94a3b8;">
<p>[Concise, actionable answer with specific details. Include source link if citing data.]</p>
</div>
</details>
</div>

**FAQ Question Examples (Use these types):**
- "What is the pricing difference between X and Y?" (Pricing)
- "Can I migrate from X to Y easily?" (Practical concern)
- "Does X support [specific feature]?" (Feature verification)
- "What are the system requirements for X?" (Technical specs)
- "Is X free for open source projects?" (Licensing)

**FAQ RULES:**
- Questions must be SPECIFIC, not generic
- Answers must include real data or source links where applicable
- NO fake questions like "Why is X the best?" (sounds like marketing)
- H2 heading MUST start with "FAQ" (not "Frequently Asked Questions")

=== BENCHMARK METHODOLOGY SECTION (MANDATORY when using "our testing" data!) ===
If you reference ANY data from "our testing/benchmark/analysis", you MUST include this section.
Place it AFTER FAQ section, BEFORE Final Verdict.

<div id="benchmark-methodology" style="background: linear-gradient(135deg, #1a1a2e 0%, #0f172a 100%); padding: 24px; border-radius: 12px; margin: 32px 0; border: 1px solid #3b82f6;">
<h3 style="color: #00d9ff; margin: 0 0 20px 0; font-size: 1.2em;">📊 Benchmark Methodology</h3>

<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 20px;">
<div style="background: #1e293b; padding: 16px; border-radius: 8px;">
<div style="color: #94a3b8; font-size: 0.85em; margin-bottom: 4px;">Test Environment</div>
<div style="color: #e8e8e8; font-weight: 600;">MacBook Pro M3, 16GB RAM</div>
</div>
<div style="background: #1e293b; padding: 16px; border-radius: 8px;">
<div style="color: #94a3b8; font-size: 0.85em; margin-bottom: 4px;">Test Period</div>
<div style="color: #e8e8e8; font-weight: 600;">January 15-22, 2026</div>
</div>
<div style="background: #1e293b; padding: 16px; border-radius: 8px;">
<div style="color: #94a3b8; font-size: 0.85em; margin-bottom: 4px;">Sample Size</div>
<div style="color: #e8e8e8; font-weight: 600;">100+ code completions</div>
</div>
</div>

<table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
<thead>
<tr style="border-bottom: 2px solid #3b82f6;">
<th style="text-align: left; padding: 12px; color: #00d9ff;">Metric</th>
<th style="text-align: center; padding: 12px; color: #00d9ff;">[Tool A]</th>
<th style="text-align: center; padding: 12px; color: #00d9ff;">[Tool B]</th>
</tr>
</thead>
<tbody>
<tr style="border-bottom: 1px solid #334155;">
<td style="padding: 12px; color: #e8e8e8;">Response Time (avg)</td>
<td style="text-align: center; padding: 12px; color: #10b981; font-weight: 600;">0.8s</td>
<td style="text-align: center; padding: 12px; color: #94a3b8;">1.2s</td>
</tr>
<tr style="border-bottom: 1px solid #334155;">
<td style="padding: 12px; color: #e8e8e8;">Code Accuracy</td>
<td style="text-align: center; padding: 12px; color: #10b981; font-weight: 600;">92%</td>
<td style="text-align: center; padding: 12px; color: #94a3b8;">89%</td>
</tr>
<tr style="border-bottom: 1px solid #334155;">
<td style="padding: 12px; color: #e8e8e8;">Context Understanding</td>
<td style="text-align: center; padding: 12px; color: #94a3b8;">8.5/10</td>
<td style="text-align: center; padding: 12px; color: #10b981; font-weight: 600;">9.0/10</td>
</tr>
</tbody>
</table>

<div style="color: #64748b; font-size: 0.85em; line-height: 1.6;">
<strong style="color: #94a3b8;">Testing Methodology:</strong> We tested [X] code completion requests across React, Python, and TypeScript projects. Each tool was given identical prompts. Response time measured from request to first token. Accuracy determined by successful compilation and manual review.<br><br>
<strong style="color: #94a3b8;">Limitations:</strong> Results may vary based on hardware, network conditions, and code complexity. This represents our specific testing environment.
</div>
</div>

**BENCHMARK SECTION RULES:**
- Replace [Tool A], [Tool B] with actual tool names being compared
- Update metrics and values with your ACTUAL test results
- Be HONEST about limitations
- Include at least 3 metrics in the comparison table
- This section MUST have id="benchmark-methodology" for anchor links to work

=== SOURCE VERIFICATION RULES (CRITICAL - NO HALLUCINATED URLS!) ===
⚠️ NEVER GENERATE FAKE URLS! This is the #1 quality killer.

**ABSOLUTELY BANNED - Will cause content rejection:**
- ❌ Fake news article URLs (tomshardware.com/tech-industry/..., techcrunch.com/2026/...)
- ❌ Made-up blog post URLs
- ❌ Any URL you cannot verify exists RIGHT NOW
- ❌ "Based on our research" without methodology
- ❌ Made-up percentages like "87% of developers prefer..."

**ALLOWED source citation formats:**

1. **For news/industry data - TEXT ONLY, no links:**
   ✅ "According to Tom's Hardware reports (January 2026)"
   ✅ "Per TSMC investor briefings"
   ✅ "Industry analysts estimate..."

2. **For GitHub stats - ONLY if repo exists:**
   ✅ "47k GitHub stars <a href='https://github.com/org/repo'>(GitHub)</a>"

3. **For official product info - Homepage ONLY:**
   ✅ "$20/month <a href='https://cursor.sh/pricing'>(Cursor)</a>"

4. **For your own testing data:**
   ✅ "In our 30-day benchmark: [data] <span style='color:#94a3b8;'>(Bytepulse testing)</span>"
   ✅ Include test conditions: "MacBook Pro M3, 16GB RAM"

**Remember:** It's better to have NO link than a BROKEN link!

=== IMPORTANT ===
- Use REAL product URLs for all buttons/CTAs (see list above)
- Add target="_blank" rel="noopener" to all external links
- Stick to blue/cyan color palette only
- No rainbow colors - professional, consistent look

=== OUTPUT FORMAT (MUST FOLLOW EXACTLY!) ===
Output in this EXACT format with markers:

---SEO-META---
FOCUS_KEYPHRASE: [2-4 word keyphrase that MUST appear in title, e.g., "Linear vs Jira" or "Cursor AI Guide"]
META_DESCRIPTION: [150-160 chars, include focus keyphrase, compelling hook]
---CONTENT---
<h1>Your Headline Analyzer Optimized Title</h1>
[Rest of HTML content...]

CRITICAL RULES:
- FOCUS_KEYPHRASE must be 2-4 words that appear in the H1 title
- FOCUS_KEYPHRASE must also appear in at least 2 H2 headings
- META_DESCRIPTION must contain the FOCUS_KEYPHRASE
- Start ---CONTENT--- section with <h1> tag
"""
        },
        ContentType.COMPARISON: """
Write a comparison blog post about: {topic}

Target keywords: {keywords}

Requirements:
- Write in HTML format
- Compare 2 or more items/tools/services
- Include H1 title
- Include 5+ H2 sections
- Include comparison tables where appropriate
- Include a FAQ section with 3+ questions
- Write 1500-2500 words
- Be objective and balanced
- Include a recommendation at the end

Output only the HTML content, no markdown.
""",
        ContentType.GUIDE: """
Write a how-to guide blog post about: {topic}

Target keywords: {keywords}

Requirements:
- Write in HTML format
- Include H1 title with "How to" or "Guide"
- Include 5+ H2 sections for steps/sections
- Include numbered or bulleted lists
- Include a FAQ section with 3+ questions
- Write 1500-2500 words
- Be clear and actionable
- Include prerequisites if applicable
- Include tips and warnings

Output only the HTML content, no markdown.
""",
        ContentType.LIST: {
            "ko": """
{topic}에 대한 아카이브형 총정리 콘텐츠를 작성하세요.

타겟 키워드: {keywords}

=== TrendPulse 블로그 컨셉 ===
타겟 독자: "투자하는 얼리어답터" - 돈의 흐름(경제)을 읽고, 앞선 기술(테크)을 소비하는 사람들
콘텐츠 유형: 나중에 다시 찾아와서 볼 만한 "총정리" 아카이브 콘텐츠

=== 필수 규칙 ===
- 반드시 한국어로 작성
- 현재 연도(2026년) 사용
- Ctrl+F로 찾기 쉬운 구조화된 정보
- 투자/기술 관점의 인사이트 포함

=== 스타일 규칙 ===
- 짧은 문단 (2-3문장) - 가독성이 생명
- 표(table)로 한눈에 비교 가능하게
- 모든 섹션에: <!-- IMAGE: 설명 -->
- <strong>으로 핵심 강조
- 총 단어 수: 1500-2500 단어 (총정리는 길어도 OK)

=== 필수 구조 ===
1. H1: 아카이브형 제목 (예: "2026년 OO 관련주 총정리", "OO 완벽 가이드")

2. 3줄 요약 박스 (최상단):
<div style="background-color:#e8f4fd;padding:20px;border-left:4px solid #0066cc;margin:20px auto;border-radius:4px;max-width:800px;">
<p style="margin:0 0 10px 0;font-weight:bold;color:#333333;font-size:1.1em;text-align:center;">⚡ 바쁜 분들을 위한 3줄 요약</p>
<ol style="margin:0;padding-left:20px;color:#333333;">
<li style="margin-bottom:8px;color:#333333;">핵심 포인트 1</li>
<li style="margin-bottom:8px;color:#333333;">핵심 포인트 2</li>
<li style="margin-bottom:8px;color:#333333;">핵심 포인트 3</li>
</ol>
</div>

3. 핵심 추천 박스 (TL;DR):
<div style="background-color:#f0f7f0;padding:20px;border:2px solid #28a745;margin:20px auto;border-radius:8px;max-width:800px;">
<p style="margin:0 0 15px 0;font-weight:bold;color:#333333;font-size:1.2em;text-align:center;">🏆 핵심 추천</p>
<ul style="margin:0;padding-left:20px;color:#333333;">
<li style="margin-bottom:10px;color:#333333;"><strong style="color:#28a745;">최고 추천:</strong> 아이템명 – 추천 이유</li>
<li style="margin-bottom:10px;color:#333333;"><strong style="color:#0066cc;">가성비 추천:</strong> 아이템명 – 추천 이유</li>
</ul>
</div>

4. 도입부: 왜 이 정보가 중요한지

5. 비교 테이블 (필수, 가운데 정렬):
<div style="overflow-x:auto;margin:20px auto;max-width:800px;">
<table style="width:100%;border-collapse:collapse;color:#333333;">
<thead><tr style="background-color:#f5f5f5;">
<th style="padding:12px;border:1px solid #ddd;color:#333333;text-align:center;">항목</th>
<th style="padding:12px;border:1px solid #ddd;color:#333333;text-align:center;">특징</th>
<th style="padding:12px;border:1px solid #ddd;color:#333333;text-align:center;">추천 대상</th>
</tr></thead>
<tbody>
<tr style="background-color:#ffffff;"><td style="padding:12px;border:1px solid #ddd;color:#333333;text-align:center;">항목1</td><td style="padding:12px;border:1px solid #ddd;color:#333333;">...</td><td style="padding:12px;border:1px solid #ddd;color:#333333;">...</td></tr>
</tbody>
</table>
</div>

6. 7-10개 H2 섹션:
   - <!-- IMAGE: 관련 이미지 (영어) -->
   - 각 항목별 상세 분석
   - 장단점, 주의사항
   - 투자/활용 관점 인사이트

7. 인사이트 박스:
<div style="background-color:#fff8e1;padding:20px;border-left:4px solid #ff9800;margin:20px auto;border-radius:4px;max-width:800px;">
<p style="margin:0 0 10px 0;font-weight:bold;color:#333333;font-size:1.1em;text-align:center;">💡 TrendPulse 인사이트</p>
<p style="margin:0;color:#333333;">여기에 독자적인 분석/전망 작성</p>
</div>

7. FAQ 섹션 (H2): 3-4개 실용적인 질문
8. 결론: 핵심 정리 + 앞으로 주목할 포인트

이미지 플레이스홀더 (영어):
<!-- IMAGE: stock market trading floor -->
<!-- IMAGE: technology gadgets on desk -->

출력: HTML만, 마크다운 없이, 코멘트 없이.
""",
            "en": """
Write an expert-level listicle for tech professionals about: {topic}

Target keywords: {keywords}

NICHE FOCUS (bytepulse.io):
- Specific niches: AI Tools, Dev Productivity, SaaS Reviews, Web3/Blockchain
- Target audience: Developers, startup founders, tech professionals
- Provide UNIQUE insights, not generic overviews

CONTENT QUALITY:
- In-depth analysis for each item (not just surface features)
- Real pros/cons from actual usage perspective
- Pricing, integrations, and practical considerations
- Compare alternatives where relevant
- Include "Best for:" recommendation for each item

IMPORTANT RULES:
- Write ONLY in English for US/UK tech audience
- Use CURRENT YEAR (2026) - NEVER 2025 or older
- Be technically accurate and honest

STYLE RULES:
- Professional, clear tone
- SHORT paragraphs (2-3 sentences)
- Use tables for feature comparisons
- Every section: <!-- IMAGE: description -->
- Total word count: 1500-2500 words

STRUCTURE:
1. H1: Specific title with number (e.g., "7 Best AI Code Assistants for React Developers in 2026")
2. Hook: Why this matters NOW for your audience
3. TL;DR box (class="tldr"): Quick picks with "Best for X" labels
4. 7-10 H2 sections, each with:
   - <!-- IMAGE: tech-focused scene -->
   - Key features (bullet list)
   - Pricing info
   - Pros/Cons
   - "Best for:" specific use case
   - Link to official site
5. Comparison table (optional)
6. FAQ section (H2): 3-4 technical questions
7. Conclusion: Final recommendations by use case

IMAGE PLACEHOLDER (tech-focused):
<!-- IMAGE: developer coding on laptop with multiple screens -->
<!-- IMAGE: modern SaaS dashboard interface -->

Output: Clean HTML only, no markdown, no commentary.
"""
        },
        ContentType.NEWS: """
Write a news analysis blog post about: {topic}

Target keywords: {keywords}

Requirements:
- Write in HTML format
- Include H1 title
- Include 5+ H2 sections
- Cover: What happened, Why it matters, Impact, What's next
- Include a FAQ section with 3+ questions
- Write 1500-2500 words
- Be factual and informative
- Include expert perspectives if relevant

Output only the HTML content, no markdown.
""",
    }

    def __init__(self, config: Optional[ContentConfig] = None) -> None:
        """Initialize ContentGenerator.

        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or ContentConfig()
        self._setup_apis()

    def _setup_apis(self) -> None:
        """Setup LLM API clients."""
        self._gemini_client = None

        # Setup Gemini (new google.genai API)
        if genai is not None:
            api_key = os.getenv("GOOGLE_AI_API_KEY")
            if api_key:
                self._gemini_client = genai.Client(api_key=api_key)
                logger.info("Gemini API configured (google.genai)")

        # OpenAI client is created on-demand

    def generate(
        self,
        topic: str,
        keywords: list[str],
        content_type: ContentType,
        category: Optional[str] = None,
        mode: str = "general",
    ) -> GeneratedContent:
        """Generate blog content for a topic.

        Args:
            topic: The topic to write about
            keywords: Target SEO keywords
            content_type: Type of content to generate
            category: Optional category for context-aware generation
            mode: Blog mode (general or tech)

        Returns:
            GeneratedContent object with the generated post
        """
        logger.info(f"Generating {content_type.value} content for: {topic} (category: {category})")

        # Load and format prompt
        prompt_template = self._load_prompt_template(content_type)
        prompt = prompt_template.format(
            topic=topic,
            keywords=", ".join(keywords),
        )

        # Add category-specific context for better content generation
        if category:
            category_context = self._get_category_context(category, topic)
            if category_context:
                prompt = category_context + "\n\n" + prompt

        # Research with Gemini Grounding for latest information
        research_data = self.research_with_grounding(
            topic=topic,
            keywords=keywords,
            language=self.config.language,
        )
        if research_data:
            # Add research data AFTER the main prompt (as reference material)
            # This ensures structural requirements (H2, FAQ) are not pushed down
            research_section = f"""

=== REFERENCE: Latest Research Data (Use for accuracy) ===
{research_data}
=== END REFERENCE ===

IMPORTANT: Use the above research data for accurate, up-to-date information (pricing, versions, dates).
But you MUST follow ALL structural requirements in the prompt above (H2 headings, FAQ section, etc.)."""
            prompt = prompt + research_section
            logger.info("Research data added to prompt (as reference)")

        # Generate content with LLM (with retry on structural failures)
        max_retries = 2
        for attempt in range(max_retries):
            if attempt > 0:
                # Add explicit structural requirements reminder for retry
                retry_prompt = prompt + """

=== CRITICAL RETRY NOTICE ===
Your previous response was REJECTED because it was missing required structural elements.
You MUST include:
1. At least 4-5 H2 headings (<h2>...</h2>) to structure the content
2. A FAQ section with at least 3 questions using proper HTML structure
3. Follow the EXACT HTML format specified in the prompt

DO NOT use Markdown. Use only HTML tags."""
                raw_response = self._call_llm(retry_prompt)
                logger.info(f"Retry attempt {attempt + 1} for content generation")
            else:
                raw_response = self._call_llm(prompt)

            # Parse SEO metadata and content (tech mode uses structured format)
            focus_keyphrase = ""
            meta_description = ""
            raw_html = raw_response

            if mode == "tech" and "---SEO-META---" in raw_response:
                # Parse structured format: ---SEO-META--- ... ---CONTENT---
                focus_keyphrase, meta_description, raw_html = self._parse_seo_format(raw_response)
                logger.debug(f"Parsed SEO format - keyphrase: {focus_keyphrase}")

            # Clean and process HTML
            html = self._clean_html(raw_html)

            # Validate content early to check for structural issues
            is_valid, errors = self._validate(html)

            # Check for critical structural failures that warrant retry
            critical_failures = [e for e in errors if "H2" in e or "FAQ" in e]
            if critical_failures and attempt < max_retries - 1:
                logger.warning(f"Critical structural issues found: {critical_failures}. Retrying...")
                continue  # Retry

            # Passed validation or final attempt - proceed
            break

        # Extract title and remove H1 from content (WordPress adds H1 automatically)
        title = self._extract_title(html) or topic
        # 제목 길이 체크: tech 모드는 전체 제목 유지, general 모드는 50자로 축약 (SEO 권장)
        if mode != "tech" and len(title) > 50:
            logger.warning(f"Title too long ({len(title)} chars): {title}")
            title = self._shorten_title(title, max_length=50)
        html = self._remove_h1(html)

        # Apply category-based color theme (H2, strong, boxes, etc.)
        html = self._apply_category_theme(html, category)

        # Sanitize external links - remove hallucinated URLs, keep only verified domains
        html = self._sanitize_external_links(html)

        # Fix benchmark anchor links - ensure proper <a href="#benchmark-methodology"> tags
        html = self._fix_benchmark_anchor_links(html)

        # Add FTC disclosure for US market affiliate content (kculture mode)
        html = self._add_ftc_disclosure(html, mode)

        # Add discount/deals section for K-Culture product content
        html = self._add_discount_section(html, topic, category or "", mode)

        # Enhance K-Food content with dynamic product images from Amazon
        if category == "K-Food":
            html = self._enhance_kfood_products(html, topic, mode)

        # Generate meta description if not parsed from structured format
        if not meta_description:
            meta_description = self._generate_meta(topic, keywords, html)

        # Count words
        word_count = self._count_words(html)

        # Final validation logging
        if not is_valid:
            logger.warning(f"Content validation warnings: {errors}")

        return GeneratedContent(
            title=title,
            html=html,
            meta_description=meta_description,
            keywords=keywords,
            word_count=word_count,
            content_type=content_type,
            focus_keyphrase=focus_keyphrase,
        )

    def _get_category_context(self, category: str, topic: str) -> str:
        """Get category-specific context to prepend to prompts.

        TrendPulse.blog 사일로 구조: 테크, 비즈니스, 생산성, 리뷰, 건강

        Args:
            category: The detected/specified category
            topic: The topic being written about

        Returns:
            Category-specific instruction string
        """
        # 건강: 바이오해킹/웰니스 트렌드 (YMYL 피하고 트렌드 관점)
        if category == "건강":
            return f"""
[카테고리: 건강 - 바이오해킹 & 웰니스 트렌드]

이 글은 "{topic}"에 대한 **웰니스/바이오해킹** 콘텐츠입니다.

=== TrendPulse 컨셉 ===
"최상의 컨디션을 유지하는 법" - 질병 치료가 아닌 퍼포먼스 최적화

=== 주의: YMYL 회피 ===
- 나쁜 예: "당뇨병 치료법" (전문가 영역, 노출 안 됨)
- 좋은 예: "실리콘밸리 CEO들의 단식 트렌드" (트렌드 영역, 클릭 잘 됨)

=== 반드시 포함할 내용 ===
1. **트렌드 배경**: 왜 이게 주목받는가
2. **실천 방법**: 따라할 수 있는 구체적 방법
3. **실리콘밸리/테크CEO 사례**: 권위 있는 사례 인용
4. **과학적 근거**: 연구결과 간단히 언급
5. **주의사항**: 개인차, 전문가 상담 권유

=== 다룰 수 있는 주제 예시 ===
- "뇌 효율을 높이는 영양제 조합(누트로픽)"
- "실리콘밸리 CEO들의 단식 트렌드"
- "콜드플런지가 뜨는 이유"
- "수면해킹: 4시간 자도 개운한 방법"

=== 톤앤매너 ===
- 트렌디하고 실험적인 톤
- "테크 업계에서 유행하는" 관점
- 호기심 자극, 시도해보고 싶게

=== 피해야 할 내용 ===
- 질병 진단/치료법 (YMYL 위험)
- 의학적 조언 (전문가 상담 권유로 대체)
- 주식/투자 분석 (금지)
"""

        # 리뷰: IT 기기 + 건강 보조 기구 (현금 파이프라인)
        elif category == "리뷰":
            return f"""
[카테고리: 리뷰 - 테크 가젯 & 웰니스 기기 리뷰]

이 글은 "{topic}"에 대한 **제품/서비스 리뷰** 콘텐츠입니다.

=== TrendPulse 컨셉 ===
"최신 도구를 활용하라" - 구매 직전 검색자 타겟 (전환율 높음)

=== 수익화 목표 ===
쿠팡 파트너스, 아마존 어필리에이트 등 제휴 마케팅 전환

=== 반드시 포함할 내용 ===
1. **제품 스펙 비교표**: 가격, 주요 사양 한눈에 비교
2. **실사용 관점 장단점**: 솔직한 평가 (단점도 명확히)
3. **추천 대상**: "이런 분께 추천" 명확히 제시
4. **가성비 분석**: 가격 대비 성능 평가
5. **대안 제품**: 비슷한 가격대 다른 옵션

=== 다룰 수 있는 주제 예시 ===
- "직장인 거북목 탈출템 베스트 5"
- "오라링(Oura Ring) vs 애플워치 수면 측정 비교"
- "2026년 스탠딩데스크 추천"
- "마사지건 가성비 순위"

=== 톤앤매너 ===
- 구매 결정에 실질적 도움이 되는 정보
- "내 돈 주고 살 만한가?"에 답하는 글
- 데스크테리어, 재택근무, 건강 개선 관점

=== 피해야 할 내용 ===
- 주식/투자 분석 (금지)
- 단순 스펙 나열 (실사용 경험 중심으로)
"""

        # 생산성: 업무 툴, 자기계발, 생산성 팁 (최고의 수익 효율)
        elif category == "생산성":
            return f"""
[카테고리: 생산성 - 스마트한 일하는 방식]

이 글은 "{topic}"에 대한 **업무 효율화/생산성** 콘텐츠입니다.

=== TrendPulse 컨셉 ===
"더 똑똑하게 일하라" - 자기계발 욕구 타겟 (가장 높은 수익 효율)

=== 수익화 목표 ===
- 노션 템플릿 판매
- SaaS 제휴 마케팅 (건당 단가 높음)
- 전자책 판매 연계

=== 반드시 포함할 내용 ===
1. **실제 활용법**: 구체적인 사용 시나리오
2. **단계별 가이드**: 따라하기 쉬운 설명
3. **무료 vs 유료 비교**: 가격 정책, 유료 가치 여부
4. **대안 툴 비교**: 비슷한 기능의 다른 서비스
5. **템플릿/예시**: 바로 적용 가능한 자료

=== 다룰 수 있는 주제 예시 ===
- "2026년형 시간 관리법"
- "성공하는 사람들의 아침 루틴"
- "ChatGPT로 업무 자동화하기"
- "노션 생산성 템플릿 추천"

=== 톤앤매너 ===
- "이걸 쓰면 업무가 이렇게 바뀐다" 실질적 변화 강조
- 직장인, 프리랜서, 1인 기업가 타겟
- ChatGPT, 노션, 자동화 툴 등 트렌디한 주제

=== 피해야 할 내용 ===
- 주식/투자 분석 (금지)
- 너무 기술적인 개발자 용어 (일반 직장인 타겟)
"""

        # 비즈니스: 기업 분석, 마케팅, 경제 이슈 해설 (브랜딩 & 권위)
        elif category == "비즈니스":
            return f"""
[카테고리: 비즈니스 - 산업 트렌드 & 커리어 인사이트]

이 글은 "{topic}"에 대한 **기업/산업 분석** 콘텐츠입니다.

=== TrendPulse 컨셉 ===
"더 나은 나를 위한 트렌드" - 블로그의 전문성과 권위를 담당

=== 타겟 독자 ===
취준생, 직장인, 기획자 등 '자기계발'에 관심 있는 구매력 높은 독자층

=== 반드시 포함할 내용 ===
1. **핵심 인사이트**: "왜 이게 중요한가?" 명확히
2. **기업 전략 분석**: 의사결정의 배경과 의미
3. **산업 트렌드**: 큰 그림에서의 위치
4. **커리어 시사점**: 취업/이직에 어떤 의미인지
5. **2026년 전망**: 올해 남은 기간 동안 어떻게 될 것인가 (2027년 이후 예측 금지)

=== 다룰 수 있는 주제 예시 ===
- "애플이 전기차를 포기한 진짜 이유"
- "반도체 패키징 기술이 중요한 이유"
- "2026년 뜨는 직업 트렌드"

=== 톤앤매너 ===
- 주가가 아닌 '기업의 전략'과 '산업의 미래' 관점
- 경제 뉴스를 읽지 않는 사람도 이해하기 쉽게
- 인사이트 중심 (단순 뉴스 전달 X)

=== 피해야 할 내용 ===
- 주가, 시총, 투자 추천 (금지)
- 단순 뉴스 요약 (해석과 인사이트 필수)
"""

        # 테크: AI + 헬스테크/슬립테크 (트래픽 유입, 높은 애드센스 단가)
        elif category == "테크":
            return f"""
[카테고리: 테크 - AI & 헬스테크 트렌드]

이 글은 "{topic}"에 대한 **기술 트렌드** 콘텐츠입니다.

=== TrendPulse 컨셉 ===
"이 기술이 우리 삶(건강/생산성)을 어떻게 바꾸나" 관점

=== 목표 ===
검색 유입 트래픽 확보 + 높은 애드센스 단가

=== 반드시 포함할 내용 ===
1. **새로운 점**: 기존 대비 무엇이 달라졌나
2. **실제 활용 사례**: 어디에 쓸 수 있나
3. **장단점 분석**: 객관적 평가
4. **경쟁 기술 비교**: vs 다른 기술/서비스
5. **2026년 전망**: 올해 어떻게 발전할 것인가 (2027년 이후 예측 금지)

=== 다룰 수 있는 주제 예시 ===
- "AI가 개인 맞춤형 영양제를 추천하는 시대"
- "슬립테크(Sleep-Tech) 시장이 뜬다"
- "ChatGPT 새 기능 분석"
- "AI 영상편집 툴 비교"

=== 톤앤매너 ===
- 개발자가 아닌 일반인도 이해 가능하게
- "이 기술이 내 삶을 어떻게 바꿀까?" 관점
- 흥미롭고 트렌디한 톤

=== 피해야 할 내용 ===
- 주식/투자 분석 (금지)
- 너무 딥한 기술 용어 (일반 독자 타겟)
"""

        # === K-Culture categories (k-pulse.blog - US market) ===

        elif category == "K-Beauty":
            return f"""
[Category: K-Beauty - Korean Skincare & Cosmetics]

This article is about "{topic}" for US readers interested in Korean beauty.

=== K-Pulse Blog Concept ===
"Your Guide to K-Culture Trends" - Help Americans discover Korean beauty products

=== Target Audience ===
US skincare enthusiasts, K-drama fans, beauty beginners wanting to try Korean products

=== READABILITY & SEO (CRITICAL!) ===
1. **Section Length**: MAX 300 words per H2 section!
   - If a section needs more content, ADD H3 subheadings to break it up
   - Example: H2 "Best Korean Sunscreens" → H3 "For Oily Skin", H3 "For Dry Skin", H3 "For Sensitive Skin"
2. **Short Paragraphs**: 2-3 sentences MAX per paragraph, then line break
3. **H3 Subheadings**: Use H3s to organize product lists, comparisons, or detailed explanations
4. **Bullet Points**: Use lists for ingredients, benefits, how-to steps

=== MUST Include ===
1. **Product Names in English**: Use romanized names (e.g., "COSRX Snail Mucin")
2. **Where to Buy**: Amazon links, YesStyle, Olive Young Global
3. **Price in USD**: Always show USD (~$XX) alongside any KRW prices
4. **Skin Type Recommendations**: "Best for oily skin", "Great for sensitive skin"
5. **How to Use**: Step-by-step application guide (Korean skincare routine context)
6. **Key Ingredients**: Explain Korean skincare ingredients (snail mucin, centella, etc.)

=== Price Format ===
IMPORTANT: When mentioning Korean prices, ALWAYS include USD equivalent:
- "15,000 KRW (~$11 USD)" NOT just "15,000원"
- Use exchange rate of ~1350 KRW per USD

=== Tone ===
- Friendly, enthusiastic but informative
- Explain Korean beauty concepts for beginners
- Use "glass skin", "10-step routine" naturally

=== HEADLINE OPTIMIZATION (CRITICAL for SEO!) ===
Your H1 title MUST score 40+ on Headline Analyzer. Follow these rules:

1. **Word Count**: 6-12 words (NOT 3-4 words!)
   - BAD: "Korean Skincare Guide" (3 words)
   - GOOD: "10 Best Korean Skincare Products for Glass Skin in 2026" (10 words)

2. **Power Words** (use at least 1):
   Ultimate, Best, Essential, Secret, Proven, Top, Amazing, Revolutionary

3. **Emotional Words** (use at least 1):
   Glowing, Radiant, Flawless, Stunning, Beautiful, Gorgeous, Transformative

4. **Headline Types** (use one):
   - List: "7 Korean Sunscreens That Won't Leave a White Cast"
   - Guide: "The Ultimate Guide to Korean Glass Skin Routine"
   - How-to: "How to Build Your Perfect 10-Step Korean Skincare Routine"

5. **Include Numbers**: Lists with numbers get 36% more engagement

=== Avoid ===
- Korean-only product names without English
- Prices in KRW only (always add USD)
- Assuming readers know Korean skincare terms
- Sections longer than 300 words without H3 subheadings
"""

        elif category == "K-Food":
            return f"""
[Category: K-Food - Korean Cuisine & Snacks]

This article is about "{topic}" for US readers curious about Korean food.

=== K-Pulse Blog Concept ===
"Taste Korea from Home" - Help Americans discover Korean flavors

=== Target Audience ===
Foodies, K-drama watchers, Asian grocery shoppers, ramen enthusiasts

=== MUST Include ===
1. **Product Names**: English name + Korean (한글) for shopping
2. **Where to Buy with SEARCH LINKS**:
   - ALWAYS include Amazon search link: <a href="https://www.amazon.com/s?k=[PRODUCT+NAME]+korean">Shop on Amazon</a>
   - Replace [PRODUCT+NAME] with URL-encoded product name (e.g., "korean+cheese", "samyang+ramen")
   - Example: <a href="https://www.amazon.com/s?k=samyang+buldak+ramen&i=grocery" target="_blank" rel="nofollow">Shop Samyang Buldak on Amazon</a>
3. **Price in USD**: Always show USD price
4. **Spice Level Warning**: 🌶️ ratings for spicy products
5. **Cooking Tips**: How to prepare, what to pair with
6. **Taste Description**: Flavor profile for unfamiliar foods

=== PRODUCT LINK FORMAT (REQUIRED!) ===
For EACH product mentioned, include a styled shopping link box:
<div class="product-link" style="background:#fff3e0;border-left:4px solid #ff9800;padding:15px;margin:20px 0;border-radius:4px;">
  <strong>🛒 Buy [Product Name]:</strong><br>
  <a href="https://www.amazon.com/s?k=[product+name]+korean&i=grocery" target="_blank" rel="nofollow" style="color:#ff6d00;">Shop on Amazon →</a>
</div>

=== Price Format ===
IMPORTANT: Always include USD:
- "$5.99 on Amazon" or "5,000 KRW (~$4 USD)"

=== Tone ===
- Fun, appetizing descriptions
- "If you loved this in K-dramas..." connections
- Relatable comparisons to Western foods

=== HEADLINE OPTIMIZATION (CRITICAL for SEO!) ===
Your H1 title MUST score 40+ on Headline Analyzer. Follow these rules:

1. **Word Count**: 6-12 words (NOT 3-4 words!)
   - BAD: "Korean Fermented Tea Guide" (4 words, score 31)
   - GOOD: "Ultimate Guide to Korean Fermented Tea: 7 Must-Try Varieties" (10 words)

2. **Power Words** (use at least 1):
   Ultimate, Essential, Complete, Best, Top, Amazing, Delicious, Authentic, Secret, Proven

3. **Emotional Words** (use at least 1):
   Mouthwatering, Irresistible, Addictive, Heavenly, Incredible, Mind-Blowing, Crave-Worthy

4. **Headline Types** (use one):
   - List: "7 Best Korean Snacks You Need to Try Right Now"
   - How-to: "How to Make Authentic Korean Fried Chicken at Home"
   - Guide: "The Ultimate Guide to Korean BBQ: Everything You Need to Know"

5. **Include Numbers**: Lists with numbers get 36% more engagement
   - "5 Must-Try", "7 Best", "10 Essential"

=== READABILITY & SEO (CRITICAL!) ===
1. **Section Length**: MAX 300 words per H2 section!
   - If a section needs more content, ADD H3 subheadings to break it up
   - Example: H2 "Best Korean Ramen" → H3 "For Spicy Lovers", H3 "For Mild Flavor Fans", H3 "Budget-Friendly Options"
2. **Short Paragraphs**: 2-3 sentences MAX per paragraph, then line break
3. **H3 Subheadings**: Use H3s to organize food lists, flavor comparisons, or cooking instructions
4. **Bullet Points**: Use lists for ingredients, taste notes, spice levels, cooking tips

=== Avoid ===
- Assuming readers have tried the food
- Korean-only descriptions
- Missing spice level warnings for hot items
"""

        elif category == "K-Pop":
            # Check if topic is about concert/tour
            topic_lower = topic.lower()
            is_concert_topic = any(kw in topic_lower for kw in ["concert", "tour", "setlist", "stadium", "arena"])

            concert_section = ""
            if is_concert_topic:
                concert_section = """
=== CONCERT/TOUR SPECIFIC (REQUIRED!) ===
Since this is about a concert/tour, you MUST include:

1. **Tour Date Schedule Table**: Create an HTML table with upcoming tour dates:
   - Use this exact format:
   <div class="tour-dates" style="margin: 25px 0;">
   <h3 style="color: #ff6b9d; margin-bottom: 15px;">📅 Tour Dates & Venues</h3>
   <table style="width: 100%; border-collapse: collapse; background: #1a1a2e; border-radius: 8px; overflow: hidden;">
   <thead>
   <tr style="background: linear-gradient(135deg, #ff6b9d 0%, #c44569 100%);">
   <th style="padding: 12px; text-align: left; color: #fff;">Date</th>
   <th style="padding: 12px; text-align: left; color: #fff;">City</th>
   <th style="padding: 12px; text-align: left; color: #fff;">Venue</th>
   <th style="padding: 12px; text-align: left; color: #fff;">Tickets</th>
   </tr>
   </thead>
   <tbody>
   <tr style="border-bottom: 1px solid #333;">
   <td style="padding: 12px; color: #e0e0e0;">Month Day, Year</td>
   <td style="padding: 12px; color: #e0e0e0;">City Name</td>
   <td style="padding: 12px; color: #e0e0e0;">Venue Name</td>
   <td style="padding: 12px;"><a href="#" style="color: #ff6b9d;">Buy Tickets</a></td>
   </tr>
   <!-- Add more rows for each date -->
   </tbody>
   </table>
   </div>

2. **Setlist Section**: Include expected/confirmed setlist if available

3. **Ticket Info Box**: Prices by tier (GA, VIP, etc.) in a styled box

4. **Venue Tips**: Stadium/arena-specific tips for fans

Use ONLY verified tour dates from official sources. If dates are not confirmed, clearly state "TBA" or "To Be Announced".
"""

            return f"""
[Category: K-Pop - Korean Music & Idol Culture]

This article is about "{topic}" for international K-Pop fans.

=== K-Pulse Blog Concept ===
"Your Ultimate K-Pop Magazine" - Exciting fan content that celebrates K-Pop culture!

=== WRITING STYLE: MAGAZINE/PROMOTIONAL ===
Write like a K-Pop fan magazine (like Weverse Magazine, Soompi, AllKPop style):
- **Exciting & Celebratory**: Use exclamation marks! Express genuine excitement!
- **Fan Language**: "Your faves", "stan", "bias", "comeback", "era" - speak their language
- **Hype Mode**: Build anticipation, create FOMO, make readers excited to engage
- **Visual Emphasis**: Use emojis strategically (✨💜🔥💖) to add energy
- **Quote Highlights**: Include memorable quotes from interviews, lyrics, or fan reactions

=== Target Audience ===
Dedicated K-Pop fans, new stans curious about groups, concert-goers, collectors

=== MUST Include ===
1. **Artist Names**: English + Korean (한글) - fans love seeing Hangul!
2. **Streaming Links**: Spotify, Apple Music, YouTube Music
3. **Official Merch**: Lightsticks, albums, photocards - where to buy in US
4. **Social Media**: Official accounts to follow
5. **Fandom Name**: Always mention the official fandom name!
{concert_section}
=== Content Sections to Include ===
1. **Hype Introduction**: Why this group/comeback/tour is a BIG DEAL right now
2. **Quick Facts Box**: Debut date, members, fandom name, label
3. **Why You Should Stan**: Compelling reasons for new fans
4. **Best Songs to Start With**: Gateway tracks for newcomers
5. **Merch Guide**: Must-have items for collectors

=== Image Note ===
IMPORTANT: Only use YouTube video thumbnails or official MV screenshots.
Do NOT use fan photos or unofficial images (copyright issues with agencies).

=== Price Format ===
For merchandise: Always USD
- "Official Lightstick: ~$50 on Amazon" / "Album (Standard): ~$25"

=== Tone & Voice ===
- **Excited & Passionate**: You're a fan writing for fans!
- **Inclusive**: Welcome new fans, don't gatekeep
- **Celebratory**: Focus on achievements, milestones, and positive moments
- **Magazine-style**: Think Cosmopolitan meets K-Pop - glossy, fun, engaging

=== HEADLINE OPTIMIZATION (CRITICAL for SEO!) ===
Your H1 title MUST score 40+ on Headline Analyzer. Follow these rules:

1. **Word Count**: 6-12 words (NOT 3-4 words!)
   - BAD: "BLACKPINK World Tour Guide" (4 words)
   - GOOD: "BLACKPINK World Tour 2026: Complete Guide to Tickets, Dates & Setlist" (10 words)

2. **Power Words** (use at least 1):
   Ultimate, Complete, Essential, Exclusive, Epic, Iconic, Legendary, Must-Know

3. **Emotional Words** (use at least 1):
   Stunning, Unforgettable, Heartwarming, Amazing, Incredible, Breathtaking, Exciting

4. **Headline Types** (use one):
   - List: "7 Reasons Why ATEEZ is Dominating K-Pop in 2026"
   - Guide: "The Complete Guide to Stanning BTS: Everything New Fans Need"
   - How-to: "How to Get Concert Tickets for TWICE World Tour"

5. **Include Numbers**: Lists with numbers get 36% more engagement

=== READABILITY & SEO (CRITICAL!) ===
1. **Section Length**: MAX 300 words per H2 section!
   - If a section needs more content, ADD H3 subheadings to break it up
   - Example: H2 "Album Discography" → H3 "Mini Albums", H3 "Full Albums", H3 "Special Editions"
2. **Short Paragraphs**: 2-3 sentences MAX per paragraph, then line break
3. **H3 Subheadings**: Use H3s to organize member profiles, albums, concert sections
4. **Bullet Points**: Use lists for member info, tracklists, tour dates, merchandise

=== Avoid ===
- Dry, analytical tone (NOT a Wikipedia article!)
- Unofficial/fan-taken photos (copyright risk!)
- Rumors, dating news, or controversies
- Negative commentary on artists or fandoms
"""

        elif category == "K-Fashion":
            return f"""
[Category: K-Fashion - Korean Style & Trends]

This article is about "{topic}" for US readers interested in Korean fashion.

=== K-Pulse Blog Concept ===
"Dress Like Your Favorite K-Stars" - Korean fashion inspiration

=== Target Audience ===
Fashion-conscious readers, K-drama fans, streetwear enthusiasts

=== MUST Include ===
1. **Brand Names**: Korean brands + where to buy internationally
2. **Price Range**: USD prices or ranges
3. **Styling Tips**: How to wear Korean fashion trends
4. **Size Guide**: Korean sizing vs US sizing notes
5. **Where to Shop**: YesStyle, Musinsa Global, ASOS Korean brands

=== Price Format ===
Always USD:
- "Around $30-50 on YesStyle"

=== Tone ===
- Stylish, aspirational
- Reference K-drama looks when relevant
- Practical for Western body types

=== HEADLINE OPTIMIZATION (CRITICAL for SEO!) ===
Your H1 title MUST score 40+ on Headline Analyzer. Follow these rules:

1. **Word Count**: 6-12 words (NOT 3-4 words!)
   - BAD: "Korean Fashion Guide" (3 words)
   - GOOD: "10 Stunning Korean Fashion Trends You Need to Try in 2026" (11 words)

2. **Power Words** (use at least 1):
   Ultimate, Essential, Stunning, Chic, Effortless, Must-Have, Trendy, Iconic

3. **Emotional Words** (use at least 1):
   Beautiful, Gorgeous, Stylish, Elegant, Dreamy, Luxurious, Aesthetic

4. **Headline Types** (use one):
   - List: "7 Korean Streetwear Brands That Are Taking Over Fashion"
   - Guide: "The Ultimate Guide to Korean Minimalist Fashion Style"
   - How-to: "How to Dress Like a K-Drama Star on a Budget"

5. **Include Numbers**: Lists with numbers get 36% more engagement

=== READABILITY & SEO (CRITICAL!) ===
1. **Section Length**: MAX 300 words per H2 section!
   - If a section needs more content, ADD H3 subheadings to break it up
   - Example: H2 "Korean Streetwear Brands" → H3 "High-End Brands", H3 "Budget-Friendly Options", H3 "K-Drama Inspired"
2. **Short Paragraphs**: 2-3 sentences MAX per paragraph, then line break
3. **H3 Subheadings**: Use H3s to organize brand lists, style categories, or shopping guides
4. **Bullet Points**: Use lists for brand names, price ranges, sizing info, shopping links

=== Avoid ===
- Korean-only sizing without conversion
- Brands unavailable internationally
"""

        return ""

    def _load_prompt_template(self, content_type: ContentType) -> str:
        """Load prompt template for content type.

        Args:
            content_type: Type of content

        Returns:
            Prompt template string
        """
        # First, try to load from file
        templates_dir = Path(__file__).parent.parent / "templates" / "prompts"
        template_file = templates_dir / f"{content_type.value}.yaml"

        if template_file.exists():
            try:
                import yaml
                with open(template_file) as f:
                    data = yaml.safe_load(f)
                    return data.get("prompt", self.DEFAULT_PROMPTS[content_type])
            except Exception as e:
                logger.debug(f"Failed to load template file: {e}")

        # Fall back to default - handle both dict (language-specific) and string formats
        prompt_data = self.DEFAULT_PROMPTS[content_type]
        if isinstance(prompt_data, dict):
            # Language-specific prompts - use config language
            lang = self.config.language
            return prompt_data.get(lang, prompt_data.get("ko", ""))
        return prompt_data

    def _call_llm(self, prompt: str) -> str:
        """Call LLM API to generate content.

        Tries primary provider first, falls back to others on error.

        Args:
            prompt: The prompt to send

        Returns:
            Generated text response
        """
        # Build provider list with fallbacks
        providers = [self.config.provider]
        fallback_order = [LLMProvider.ANTHROPIC, LLMProvider.GEMINI, LLMProvider.OPENAI]
        for p in fallback_order:
            if p not in providers:
                providers.append(p)

        last_error = None

        for provider in providers:
            try:
                llm_method = ""
                if provider == LLMProvider.ANTHROPIC:
                    # Use Claude Agent SDK only - if fails, fallback to next provider (Gemini)
                    if claude_agent_query is not None:
                        llm_method = "Claude Agent SDK"
                        result = self._call_claude_agent_sdk(prompt)
                    elif self.config.use_cli:
                        llm_method = "Claude CLI"
                        result = self._call_anthropic_cli(prompt)
                    else:
                        llm_method = "Anthropic API"
                        result = self._call_anthropic_api(prompt)

                elif provider == LLMProvider.GEMINI:
                    llm_method = "Google Gemini API"
                    result = self._call_gemini(prompt)
                else:
                    llm_method = "OpenAI API"
                    result = self._call_openai(prompt)

                logger.info(f"Content generated using: {llm_method}")
                return result
            except Exception as e:
                logger.warning(f"{provider.value} failed: {e}")
                last_error = e
                continue

        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")

    def _call_claude_agent_sdk(self, prompt: str) -> str:
        """Call Claude using Agent SDK with OAuth token.

        This is the recommended method for using Claude with OAuth authentication.

        Args:
            prompt: The prompt

        Returns:
            Generated text
        """
        if claude_agent_query is None:
            raise ImportError("claude-agent-sdk not installed. Run: pip install claude-agent-sdk")

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

        # Run async function
        result = asyncio.run(_async_query())
        if not result:
            raise RuntimeError("Claude Agent SDK returned empty response")
        return result

    def _call_anthropic_cli(self, prompt: str) -> str:
        """Call Claude via CLI with OAuth authentication.

        Works both locally (interactive OAuth) and on server (CLAUDE_CODE_OAUTH_TOKEN).

        Args:
            prompt: The prompt

        Returns:
            Generated text
        """
        # Check if claude CLI is available
        claude_path = shutil.which("claude")
        if not claude_path:
            raise RuntimeError("Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code")

        # Check OAuth token for server environment
        oauth_token = os.getenv("CLAUDE_CODE_OAUTH_TOKEN")
        if oauth_token:
            logger.debug("Using CLAUDE_CODE_OAUTH_TOKEN for server authentication")

        # Run claude CLI with --print flag for non-interactive output
        result = subprocess.run(
            [claude_path, "--print", prompt],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes for longer content
        )

        if result.returncode != 0:
            error_msg = result.stderr or "Unknown error"
            if "OAuth" in error_msg or "auth" in error_msg.lower():
                raise RuntimeError(
                    f"Claude CLI auth failed. For server usage, set CLAUDE_CODE_OAUTH_TOKEN. Error: {error_msg}"
                )
            raise RuntimeError(f"Claude CLI error: {error_msg}")

        return result.stdout.strip()

    def _call_anthropic_api(self, prompt: str) -> str:
        """Call Anthropic API directly with API key (for server deployment).

        Args:
            prompt: The prompt

        Returns:
            Generated text
        """
        if anthropic is None:
            raise ImportError("anthropic not installed. Run: pip install anthropic")

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set in environment")

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=self.config.model_anthropic,
            max_tokens=4096,
            messages=[
                {"role": "user", "content": prompt}
            ],
        )
        return message.content[0].text

    def _call_gemini(self, prompt: str) -> str:
        """Call Gemini API using the new google.genai SDK.

        Args:
            prompt: The prompt

        Returns:
            Generated text
        """
        if self._gemini_client is None:
            raise ImportError("google-genai not installed or API key not configured")

        response = self._gemini_client.models.generate_content(
            model=self.config.model_gemini,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=self.config.temperature,
            ),
        )
        return response.text

    def research_with_grounding(self, topic: str, keywords: list[str], language: str = "en") -> str:
        """Research topic using Gemini Grounding with Google Search.

        Args:
            topic: The topic to research
            keywords: Related keywords for context
            language: 'en' for English, 'ko' for Korean

        Returns:
            Research summary with latest information
        """
        if self._gemini_client is None:
            logger.warning("Gemini client not available, skipping grounding research")
            return ""

        try:
            # Setup grounding tool
            grounding_tool = genai_types.Tool(google_search=genai_types.GoogleSearch())
            config = genai_types.GenerateContentConfig(
                tools=[grounding_tool],
                temperature=0.5,
            )

            # Language-specific prompt
            if language == "ko":
                prompt = f""""{topic}"에 대해 조사해주세요.

관련 키워드: {', '.join(keywords)}

다음 정보를 포함해서 정리해주세요:
1. 최신 뉴스/업데이트 (날짜 포함)
2. 주요 기능 및 특징
3. 가격 정보 (있다면)
4. 장단점
5. 경쟁 제품/서비스 - 중요: 경쟁 제품의 최신 버전 정보 포함 (2026년 1월 기준)

검색 결과를 기반으로 사실적이고 구체적으로 작성해주세요. 항상 최신 버전 번호를 사용하세요."""
            else:
                prompt = f"""Research and summarize information about: {topic}

Related keywords: {', '.join(keywords)}

Include:
1. Latest news/updates (with dates if available)
2. Key features and capabilities
3. Pricing information (if available)
4. Pros and Cons
5. Competitors or alternatives - IMPORTANT: Include the LATEST versions of competing products (e.g., GPT-5.2, Claude 4, etc. as of January 2026)

Be specific and factual based on search results. Always use the most recent version numbers."""

            response = self._gemini_client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=prompt,
                config=config,
            )

            # Log grounding metadata
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                    metadata = candidate.grounding_metadata
                    if hasattr(metadata, 'grounding_chunks'):
                        logger.info(f"Grounding research: {len(metadata.grounding_chunks)} sources found")

            logger.info(f"Research completed for: {topic}")
            return response.text

        except Exception as e:
            logger.error(f"Grounding research failed: {e}")
            return ""

    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API.

        Args:
            prompt: The prompt

        Returns:
            Generated text
        """
        if OpenAI is None:
            raise ImportError("openai not installed")

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=self.config.model_openai,
            messages=[
                {"role": "system", "content": "You are a professional blog writer."},
                {"role": "user", "content": prompt},
            ],
            temperature=self.config.temperature,
        )
        return response.choices[0].message.content

    def _clean_html(self, raw: str) -> str:
        """Clean raw LLM output to valid HTML.

        Args:
            raw: Raw LLM response

        Returns:
            Cleaned HTML
        """
        # Remove markdown code blocks
        cleaned = re.sub(r"```html\s*", "", raw)
        cleaned = re.sub(r"```\s*", "", cleaned)

        # Remove <style> tags and their content (LLM sometimes adds CSS)
        cleaned = re.sub(r"<style[^>]*>.*?</style>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)

        # Remove <script> tags and their content (safety)
        cleaned = re.sub(r"<script[^>]*>.*?</script>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)

        # Remove file path references (CLI output artifacts)
        cleaned = re.sub(r"The file has been saved to:.*$", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"`/Users/[^`]+`", "", cleaned)
        cleaned = re.sub(r"/Users/\S+\.html", "", cleaned)

        # Remove checklist/instruction patterns (✅ **Title** format)
        cleaned = re.sub(r"✅\s*\*\*[^*]+\*\*\s*[–-]\s*[^\n<]+\n?", "", cleaned)
        cleaned = re.sub(r"^\s*✅[^\n<]*\n", "", cleaned, flags=re.MULTILINE)

        # Remove AI prefacing text - find where HTML actually starts
        # Look for common HTML start patterns
        html_start_patterns = [
            r'<!DOCTYPE',
            r'<html',
            r'<h1[^>]*>',
            r'<div[^>]*class=["\']tldr',
            r'<article',
        ]

        for pattern in html_start_patterns:
            match = re.search(pattern, cleaned, re.IGNORECASE)
            if match:
                cleaned = cleaned[match.start():]
                break

        # Remove common AI response prefixes (English meta-commentary)
        prefixes_to_remove = [
            r"^I've created.*?:\s*",
            r"^Here's the.*?:\s*",
            r"^Here is the.*?:\s*",
            r"^Below is.*?:\s*",
            r"^The following.*?:\s*",
            r"^I'll create.*?:\s*",
            r"^Let me create.*?:\s*",
            r"^I'll write.*?:\s*",
            r"^Let me write.*?:\s*",
            r"^Based on.*?:\s*",
            r"^Based on my knowledge.*?:\s*",
            r"^Using my knowledge.*?:\s*",
            r"^I will create.*?:\s*",
            r"^I will write.*?:\s*",
            r"^Here is a.*?:\s*",
            r"^This is a.*?:\s*",
        ]

        for prefix in prefixes_to_remove:
            cleaned = re.sub(prefix, "", cleaned, flags=re.IGNORECASE | re.DOTALL)

        # Remove trailing AI commentary/summary
        # Find where HTML content ends (last closing tag)
        suffixes_to_remove = [
            r"---\s*\*\*Key features.*$",
            r"---\s*\*\*Features.*$",
            r"---\s*✅.*$",
            r"\*\*Key features of this post.*$",
            r"The HTML is clean and ready.*$",
            r"This post includes.*$",
            r"I hope this helps.*$",
            r"Let me know if.*$",
            r"Feel free to.*$",
            r"This blog post.*?follows.*$",
            r"The post is.*$",
        ]

        for suffix in suffixes_to_remove:
            cleaned = re.sub(suffix, "", cleaned, flags=re.IGNORECASE | re.DOTALL)

        # Find the last HTML closing tag and remove everything after it
        # Match common closing tags, then capture any trailing non-HTML text
        last_tag_pattern = r'(</(?:div|section|article|p|ul|ol|h[1-6]|main|footer|body|html)>)(?:\s*)((?:(?!</).)*?)$'
        last_tag_match = re.search(last_tag_pattern, cleaned, re.IGNORECASE | re.DOTALL)
        if last_tag_match:
            remaining = last_tag_match.group(2).strip()
            # If remaining content looks like AI commentary (has ** or ✅ or --- or text > 50 chars)
            if remaining and (re.search(r'\*\*|✅|---|file|saved|created', remaining, re.IGNORECASE) or len(remaining) > 50):
                cleaned = cleaned[:last_tag_match.end(1)]

        # Final cleanup: remove any remaining markdown bold markers
        # but only outside of HTML tags
        cleaned = re.sub(r'\*\*([^*<>]+)\*\*', r'\1', cleaned)

        # Remove leading/trailing whitespace
        cleaned = cleaned.strip()

        return cleaned

    def _sanitize_external_links(self, html: str) -> str:
        """Remove potentially hallucinated external links, keeping only verified domains.

        LLMs often generate plausible-looking but non-existent URLs (hallucinations).
        This function converts unverified external links to plain text while
        preserving links to known-safe domains.

        Args:
            html: HTML content with potentially fake external links

        Returns:
            HTML with unverified links converted to plain text citations
        """
        # Whitelist of verified, safe domains that we trust
        # These are official product sites, GitHub, etc.
        safe_domains = [
            # Official tools & products
            r'github\.com',
            r'gitlab\.com',
            r'stackoverflow\.com',
            r'survey\.stackoverflow\.co',
            r'npmjs\.com',
            r'pypi\.org',
            # Official product sites (homepages only)
            r'cursor\.sh',
            r'linear\.app',
            r'notion\.so',
            r'figma\.com',
            r'vercel\.com',
            r'netlify\.com',
            r'supabase\.com',
            r'firebase\.google\.com',
            r'aws\.amazon\.com',
            r'docker\.com',
            r'anthropic\.com',
            r'openai\.com',
            r'google\.com',
            r'microsoft\.com',
            r'apple\.com',
            r'nvidia\.com',
            r'amd\.com',
            r'intel\.com',
            r'tsmc\.com',
            # Our own site
            r'bytepulse\.io',
            r'trendpulse\.blog',
        ]

        # Create pattern to match safe domains
        safe_pattern = '|'.join(safe_domains)

        def replace_link(match):
            """Replace unverified links with plain text."""
            full_tag = match.group(0)
            href = match.group(1)
            link_text = match.group(2)

            # Keep internal anchor links (starting with #)
            if href.startswith('#'):
                return full_tag

            # Keep relative links (internal site navigation)
            if href.startswith('/') and not href.startswith('//'):
                return full_tag

            # Check if href matches any safe domain
            if re.search(safe_pattern, href, re.IGNORECASE):
                # Safe domain - keep the link
                return full_tag

            # Unsafe/unverified domain - convert to plain text citation
            # Extract source name from link text if possible
            source_name = re.sub(r'<[^>]+>', '', link_text).strip()
            if source_name:
                # Keep the source name as styled text (not a link)
                return f'<span style="color: #94a3b8; font-size: 0.85em;">({source_name})</span>'
            else:
                # No meaningful text - remove entirely
                return ''

        # Match anchor tags with href and content
        # Pattern: <a href="URL" ...>content</a>
        link_pattern = r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>'

        result = re.sub(link_pattern, replace_link, html, flags=re.IGNORECASE | re.DOTALL)

        # Count changes for logging
        original_links = len(re.findall(link_pattern, html, re.IGNORECASE | re.DOTALL))
        remaining_links = len(re.findall(r'<a\s+[^>]*href=', result, re.IGNORECASE))
        removed_count = original_links - remaining_links

        if removed_count > 0:
            logger.info(f"Sanitized {removed_count} unverified external links (kept {remaining_links} safe links)")

        return result

    def _fix_benchmark_anchor_links(self, html: str) -> str:
        """Post-process to ensure benchmark/methodology anchor links are properly implemented.

        LLMs often fail to generate proper anchor tags, outputting "(our benchmark ↓)"
        as plain text instead of clickable links. This function:
        1. Ensures research/methodology sections have proper id="benchmark-methodology"
        2. Converts "(our benchmark ↓)" text into proper anchor links

        Args:
            html: HTML content with potentially missing anchor links

        Returns:
            HTML with proper anchor links to methodology section
        """
        import re

        # Step 1: Ensure methodology section has proper id
        # Use a more targeted approach - find divs containing specific methodology text
        # and add id to them. Avoid TL;DR, Quick Verdict, etc.

        # Keywords that indicate methodology sections (positive match)
        methodology_keywords = [
            r'How\s+We\s+Researched',
            r'How\s+We\s+Tested',
            r'How\s+We\s+Analyzed',
            r'Research\s+Methodology',
            r'Benchmark\s+Methodology',
            r'Testing\s+Methodology',
            r'Our\s+Testing\s+Methodology',
            r'Testing\s+Environment',
            r'Test\s+Environment',
            r'Test\s+Setup',
            r'Data\s+Sources',
        ]

        # Keywords that indicate NON-methodology sections (negative match - skip these)
        excluded_keywords = [
            r'TL;?DR',
            r'Quick\s+Verdict',
            r'Quick\s+Summary',
            r'Final\s+Verdict',
            r'Key\s+Takeaway',
            r'Bottom\s+Line',
        ]

        # Check if anchor already exists
        anchor_exists = 'benchmark-methodology' in html

        if not anchor_exists:
            # Find methodology section and insert anchor element before it
            # WordPress sanitizes id attributes on divs, so we use <a name=""> instead
            # This is the traditional HTML anchor method that WordPress allows

            for kw in methodology_keywords:
                # Look for h3/h4 headings containing methodology keywords
                heading_pattern = rf'(<h[34][^>]*>[\s\S]*?)({kw})'
                match = re.search(heading_pattern, html, re.IGNORECASE)
                if match:
                    # Insert anchor element right before the heading
                    # Find the div containing this heading
                    full_pattern = rf'(<div[^>]*>[\s\S]*?)(<h[34][^>]*>[\s\S]*?{kw})'
                    full_match = re.search(full_pattern, html, re.IGNORECASE)
                    if full_match:
                        # Insert Gutenberg block anchor - WordPress preserves id in Gutenberg blocks
                        # Use invisible heading with anchor support
                        anchor = '<!-- wp:heading {"anchor":"benchmark-methodology","className":"screen-reader-text"} -->\n<h2 class="wp-block-heading screen-reader-text" id="benchmark-methodology"></h2>\n<!-- /wp:heading -->\n'
                        insert_pos = full_match.start(1)
                        div_tag_end = html.find('>', insert_pos) + 1
                        html = html[:div_tag_end] + anchor + html[div_tag_end:]
                        logger.debug(f"Added anchor 'benchmark-methodology' before section with: {kw}")
                        anchor_exists = True
                        break

            # If no heading found, try to find the section by text content
            if not anchor_exists:
                for kw in methodology_keywords:
                    pattern = rf'(<div[^>]*style="[^"]*(?:background|border)[^"]*"[^>]*>)([\s\S]*?{kw})'
                    match = re.search(pattern, html, re.IGNORECASE)
                    if match:
                        # Check this isn't an excluded section
                        content_preview = match.group(2)[:200]
                        is_excluded = any(re.search(excl, content_preview, re.IGNORECASE)
                                         for excl in excluded_keywords)
                        if not is_excluded:
                            # Insert Gutenberg block anchor - WordPress preserves id in Gutenberg blocks
                            anchor = '<!-- wp:heading {"anchor":"benchmark-methodology","className":"screen-reader-text"} -->\n<h2 class="wp-block-heading screen-reader-text" id="benchmark-methodology"></h2>\n<!-- /wp:heading -->\n'
                            html = html[:match.start(1)] + anchor + html[match.start(1):]
                            logger.debug(f"Added anchor 'benchmark-methodology' before div with: {kw}")
                            anchor_exists = True
                            break

        # Step 2: Convert "(our benchmark ↓)" text into proper anchor links
        # Only convert if we have a methodology anchor to link to
        if 'benchmark-methodology' in html:
            benchmark_text_patterns = [
                # "(our benchmark ↓)" - most common
                (r'\(our\s+benchmark\s*↓?\)',
                 '<a href="#benchmark-methodology" style="color: #3b82f6; font-size: 0.85em; text-decoration: none;">our benchmark ↓</a>'),
                # "(our testing ↓)"
                (r'\(our\s+testing\s*↓?\)',
                 '<a href="#benchmark-methodology" style="color: #3b82f6; font-size: 0.85em; text-decoration: none;">our testing ↓</a>'),
                # "(our analysis ↓)"
                (r'\(our\s+analysis\s*↓?\)',
                 '<a href="#benchmark-methodology" style="color: #3b82f6; font-size: 0.85em; text-decoration: none;">our analysis ↓</a>'),
                # "our benchmark" without parentheses but with arrow
                (r'our\s+benchmark\s*↓',
                 '<a href="#benchmark-methodology" style="color: #3b82f6; font-size: 0.85em; text-decoration: none;">our benchmark ↓</a>'),
                # "(see methodology below)" or similar
                (r'\(see\s+methodology\s*(?:below|↓)?\)',
                 '<a href="#benchmark-methodology" style="color: #3b82f6; font-size: 0.85em; text-decoration: none;">see methodology ↓</a>'),
            ]

            converted_count = 0
            for pattern, replacement in benchmark_text_patterns:
                matches = len(re.findall(pattern, html, re.IGNORECASE))
                if matches > 0:
                    html = re.sub(pattern, replacement, html, flags=re.IGNORECASE)
                    converted_count += matches

            if converted_count > 0:
                logger.info(f"Converted {converted_count} benchmark references to anchor links")

        return html

    def _parse_seo_format(self, response: str) -> tuple[str, str, str]:
        """Parse structured SEO format from LLM response.

        Expected format:
        ---SEO-META---
        FOCUS_KEYPHRASE: [keyphrase]
        META_DESCRIPTION: [description]
        ---CONTENT---
        <h1>...</h1>
        ...

        Args:
            response: Raw LLM response

        Returns:
            Tuple of (focus_keyphrase, meta_description, html_content)
        """
        focus_keyphrase = ""
        meta_description = ""
        html_content = response

        # Split by markers
        if "---SEO-META---" in response and "---CONTENT---" in response:
            parts = response.split("---CONTENT---", 1)
            if len(parts) == 2:
                meta_section = parts[0]
                html_content = parts[1].strip()

                # Extract FOCUS_KEYPHRASE
                keyphrase_match = re.search(
                    r'FOCUS_KEYPHRASE:\s*(.+?)(?:\n|$)',
                    meta_section,
                    re.IGNORECASE
                )
                if keyphrase_match:
                    focus_keyphrase = keyphrase_match.group(1).strip()
                    # Remove quotes if present
                    focus_keyphrase = focus_keyphrase.strip('"\'')

                # Extract META_DESCRIPTION
                meta_match = re.search(
                    r'META_DESCRIPTION:\s*(.+?)(?:\n|$)',
                    meta_section,
                    re.IGNORECASE
                )
                if meta_match:
                    meta_description = meta_match.group(1).strip()
                    meta_description = meta_description.strip('"\'')

        return focus_keyphrase, meta_description, html_content

    def _extract_title(self, html: str) -> Optional[str]:
        """Extract title from H1 tag.

        Args:
            html: HTML content

        Returns:
            Title text or None
        """
        match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
        if match:
            # Remove any nested tags
            title = re.sub(r"<[^>]+>", "", match.group(1))
            return title.strip()
        return None

    def _shorten_title(self, title: str, max_length: int = 60) -> str:
        """Shorten title to fit in one line while keeping SEO value.

        Args:
            title: Original title
            max_length: Maximum character length (default 60 for SEO)

        Returns:
            Shortened title with good SEO balance
        """
        if len(title) <= max_length:
            return title

        # VS comparison pattern: keep "A vs B: Subtitle" format for SEO
        # e.g., "Apple vs Nvidia: The Battle for TSMC Capacity in 2026" -> "Apple vs Nvidia: 2026 TSMC Capacity Analysis"
        vs_match = re.search(r'^([A-Za-z0-9_!.\s]+\s+vs\s+[A-Za-z0-9_!.\s]+)', title, re.IGNORECASE)
        if vs_match:
            vs_part = vs_match.group(1).strip()
            # Remove trailing common words from VS part
            vs_part = re.sub(r'\s+(APIs?|in|for|with|The|A|An)$', '', vs_part, flags=re.IGNORECASE).strip()

            # Try to keep year and key descriptor
            year_match = re.search(r'(20\d{2})', title)
            year = year_match.group(1) if year_match else ""

            # Extract key words after colon/dash for subtitle
            subtitle_match = re.search(r'[:\-–]\s*(.+)$', title)
            if subtitle_match:
                subtitle = subtitle_match.group(1).strip()
                # Keep important words from subtitle
                important_words = re.findall(r'\b(Analysis|Guide|Comparison|Review|Benchmark|Performance|Pricing|Complete|Detailed|Battle|Capacity|Testing)\b', subtitle, re.IGNORECASE)
                if important_words and year:
                    new_title = f"{vs_part}: {year} {' '.join(important_words[:2])}"
                elif important_words:
                    new_title = f"{vs_part}: {' '.join(important_words[:2])}"
                elif year:
                    new_title = f"{vs_part} {year}"
                else:
                    new_title = vs_part
            else:
                new_title = f"{vs_part} {year}".strip() if year else vs_part

            if len(new_title) <= max_length and len(new_title) >= 20:
                logger.info(f"Title shortened (VS pattern): '{title}' -> '{new_title}'")
                return new_title

        # "A와 B" 또는 "A: B" 패턴이면 첫 부분만 사용
        for separator in ["와 ", "과 ", ": ", " - ", " – "]:
            if separator in title:
                first_part = title.split(separator)[0]
                if len(first_part) <= max_length and len(first_part) >= 10:
                    logger.info(f"Title shortened: '{title}' -> '{first_part}'")
                    return first_part

        # 불필요한 수식어 제거
        remove_words = [
            "완벽 가이드", "완벽한 ", "실전 ", "미니멀 ", "효과적인 ", "강력한 ",
            "의 실전 노하우", "의 노하우", " 노하우",
            "시스템", " 방법", "하는 법",
            "관리한 ", "개발자의 ",
            " 완벽 가이드", " 가이드", " 활용법",
        ]

        shortened = title
        for word in remove_words:
            if len(shortened) > max_length:
                shortened = shortened.replace(word, "")

        # 여전히 길면 핵심만 남기기
        if len(shortened) > max_length:
            parts = shortened.split()
            if len(parts) > 4:
                shortened = " ".join(parts[:4])
                if len(shortened) > max_length:
                    shortened = " ".join(parts[:3])

        # 어색하게 잘리는 접속사/기호/짧은 단어 제거 (단어 단위로 체크)
        # 기호는 endswith, 단어는 정확한 마지막 단어로 체크
        bad_symbol_endings = [":", "-", "–", ",", "(", "["]
        bad_word_endings = ["와", "과", "및", "의", "를", "을", "에", "and", "or", "the", "a", "for", "to", "in", "on", "vs"]

        for ending in bad_symbol_endings:
            if shortened.endswith(ending):
                shortened = shortened[:-len(ending)].strip()

        # 단어 단위로 마지막 단어 체크
        words = shortened.split()
        if words and words[-1].lower() in bad_word_endings:
            shortened = " ".join(words[:-1])

        # 마지막으로 max_length로 자르되, 단어 중간에서 자르지 않기
        if len(shortened) > max_length:
            cut_pos = shortened[:max_length].rfind(" ")
            if cut_pos > max_length // 2:
                shortened = shortened[:cut_pos]
            else:
                shortened = shortened[:max_length-1] + "…"

            # 다시 어색한 끝 체크 (단어 단위)
            for ending in bad_symbol_endings:
                if shortened.endswith(ending):
                    shortened = shortened[:-len(ending)].strip()
            words = shortened.split()
            if words and words[-1].lower() in bad_word_endings:
                shortened = " ".join(words[:-1])

        logger.info(f"Title shortened: '{title}' -> '{shortened}'")
        return shortened

    def _remove_h1(self, html: str) -> str:
        """Remove H1 tag from HTML content.

        WordPress automatically renders post title as H1,
        so we need to remove H1 from content to avoid duplication.

        Args:
            html: HTML content

        Returns:
            HTML with H1 removed
        """
        # Remove H1 tag and its content
        cleaned = re.sub(r"<h1[^>]*>.*?</h1>\s*", "", html, flags=re.IGNORECASE | re.DOTALL)
        return cleaned.strip()

    def _apply_category_theme(self, html: str, category: Optional[str] = None) -> str:
        """Apply category-based accent colors only.

        본문 색상은 유지, 강조 요소만 카테고리별로 변경.

        Args:
            html: HTML content
            category: Post category for color selection

        Returns:
            HTML with category-themed accent colors
        """
        # 카테고리별 강조 색상 (다크 테마 배경에서 눈에 잘 보이는 밝은 색)
        category_accents = {
            "생산성": {
                "gradient": "#a78bfa,#60a5fa",  # 보라 → 블루 (기존 유지)
                "accent": "#c4b5fd",             # 밝은 보라
            },
            "테크": {
                "gradient": "#06b6d4,#3b82f6",  # 시안 → 블루
                "accent": "#67e8f9",             # 밝은 시안
            },
            "비즈니스": {
                "gradient": "#f59e0b,#fbbf24",  # 앰버 → 골드
                "accent": "#fcd34d",             # 밝은 골드
            },
            "리뷰": {
                "gradient": "#ec4899,#f97316",  # 핑크 → 오렌지
                "accent": "#f9a8d4",             # 밝은 핑크
            },
            "건강": {
                "gradient": "#10b981,#22d3ee",  # 에메랄드 → 시안
                "accent": "#6ee7b7",             # 밝은 민트
            },
            # K-Culture categories (k-pulse.blog)
            "K-Beauty": {
                "gradient": "#f472b6,#ec4899",  # 핑크 계열 (뷰티)
                "accent": "#f9a8d4",
            },
            "K-Food": {
                "gradient": "#fb923c,#f97316",  # 오렌지 (음식, 따뜻함)
                "accent": "#fdba74",
            },
            "K-Pop": {
                "gradient": "#c084fc,#a855f7",  # 보라 (아이돌, 화려함)
                "accent": "#d8b4fe",
            },
            "K-Fashion": {
                "gradient": "#2dd4bf,#14b8a6",  # 틸 (패션, 세련됨)
                "accent": "#5eead4",
            },
        }

        # 기본 (보라-블루, 생산성과 동일)
        default_accent = {
            "gradient": "#a78bfa,#60a5fa",
            "accent": "#c4b5fd",
        }

        colors = category_accents.get(category, default_accent)

        result = html

        # 1. H2 그라데이션
        h2_style = (
            "font-size:1.5em;"
            "margin:40px auto 20px auto;"
            "max-width:800px;"
            f"background:linear-gradient(135deg,{colors['gradient']});"
            "-webkit-background-clip:text;"
            "-webkit-text-fill-color:transparent;"
            "background-clip:text;"
        )

        def replace_h2(match):
            tag_content = match.group(1)
            tag_content = re.sub(r'\s*style="[^"]*"', '', tag_content)
            return f'<h2{tag_content} style="{h2_style}">'

        result = re.sub(r'<h2([^>]*)>', replace_h2, result, flags=re.IGNORECASE)

        # 2. strong 강조 색상 (기존 style 속성 유무와 관계없이 교체)
        result = re.sub(
            r'<strong[^>]*>([^<]+)</strong>',
            f'<strong style="color:{colors["accent"]}">\\1</strong>',
            result
        )

        # 3. 링크 색상
        result = result.replace('color:#64b5f6', f'color:{colors["accent"]}')

        logger.debug(f"Applied {category or 'default'} accent colors")
        return result

    def _generate_meta(
        self,
        topic: str,
        keywords: list[str],
        html: str,
    ) -> str:
        """Generate meta description for Korean blog.

        Args:
            topic: The topic
            keywords: Target keywords
            html: Full HTML content

        Returns:
            Meta description (150-160 chars) in Korean
        """
        # 3줄 요약 박스와 div를 건너뛰고 실제 본문 p 태그에서 추출
        # 첫 번째 H2 이후의 p 태그를 찾기
        h2_match = re.search(r"</h2>", html, re.IGNORECASE)
        if h2_match:
            after_h2 = html[h2_match.end():]
            p_match = re.search(r"<p[^>]*>(.*?)</p>", after_h2, re.IGNORECASE | re.DOTALL)
            if p_match:
                text = re.sub(r"<[^>]+>", "", p_match.group(1)).strip()
                # 이모지 제거
                text = re.sub(r"[^\w\s가-힣.,!?()\"']", "", text)
                if len(text) > 155:
                    text = text[:152] + "..."
                if len(text) >= 50:
                    return text[:160]

        # Fallback: 한국어로 더 풍부하게 생성 (100-150자 목표)
        if keywords and len(keywords) >= 2:
            keyword_str = ", ".join(keywords[:3])
            base = f"{topic}의 핵심 포인트를 정리했습니다. {keyword_str} 등 실용적인 정보와 트렌드를 확인해보세요."
        elif keywords:
            base = f"{topic}에 대해 알아야 할 모든 것을 정리했습니다. {keywords[0]}부터 실전 활용법까지 확인해보세요."
        else:
            base = f"{topic}에 대해 알아야 할 핵심 정보를 정리했습니다. 최신 트렌드와 실용적인 팁을 확인해보세요."
        return base[:160]

    def _count_words(self, html: str) -> int:
        """Count words in HTML content.

        Args:
            html: HTML content

        Returns:
            Word count
        """
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", html)
        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text).strip()
        # Count words
        words = text.split()
        return len(words)

    def _add_ftc_disclosure(self, html: str, mode: str) -> str:
        """Add FTC affiliate disclosure for US market content.

        Required for US-targeted affiliate content (FTC compliance).
        Amazon accounts can be suspended for missing disclosure.

        Args:
            html: HTML content
            mode: Blog mode (only 'kculture' adds disclosure)

        Returns:
            HTML with FTC disclosure prepended (if applicable)
        """
        if mode != "kculture":
            return html

        disclosure = '''<div class="ftc-disclosure" style="background-color: #1a1a2e; border-left: 4px solid #f472b6; padding: 15px 20px; margin-bottom: 25px; border-radius: 4px; font-size: 14px; color: #cbd5e1;">
<strong style="color: #f9a8d4;">Transparency Note:</strong> This post contains affiliate links. If you purchase through these links, we may earn a small commission at no extra cost to you. This helps support our content. Thank you for your support!
</div>

'''
        return disclosure + html

    def _add_discount_section(
        self,
        html: str,
        topic: str,
        category: str,
        mode: str,
    ) -> str:
        """Add discount/deals section for K-Culture product content.

        Finds real-time deals and adds discount tips to help readers save money.

        Args:
            html: HTML content
            topic: Topic/product name
            category: K-Culture category
            mode: Blog mode

        Returns:
            HTML with discount section inserted before FAQ/conclusion
        """
        if mode != "kculture":
            return html

        if DiscountFinder is None or generate_discount_html is None:
            logger.warning("DiscountFinder not available")
            return html

        try:
            finder = DiscountFinder()
            discount_info = finder.find_discount(topic, category=category)

            if not discount_info.tips and not discount_info.sale_price:
                return html  # No discount info to add

            discount_html = generate_discount_html(discount_info, topic)

            if not discount_html:
                return html

            # Add section header
            section_html = f'''
<h2>💰 Where to Buy & How to Save</h2>
{discount_html}
'''
            # Insert before FAQ section or at the end before closing
            # Look for FAQ section
            faq_patterns = [
                r'<h2[^>]*>.*?(?:FAQ|Frequently Asked|Common Questions).*?</h2>',
                r'<h2[^>]*>.*?(?:Final Verdict|Conclusion|The Bottom Line).*?</h2>',
            ]

            for pattern in faq_patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    insert_pos = match.start()
                    html = html[:insert_pos] + section_html + html[insert_pos:]
                    logger.info("Added discount section before FAQ/Conclusion")
                    return html

            # If no FAQ, insert before last closing tag
            # Find the last </div> or end of content
            last_h2 = html.rfind('</h2>')
            if last_h2 != -1:
                # Find the end of that section
                next_h2 = html.find('<h2', last_h2 + 5)
                if next_h2 != -1:
                    html = html[:next_h2] + section_html + html[next_h2:]
                else:
                    # Append at end
                    html = html + section_html
                logger.info("Added discount section at end")

            return html

        except Exception as e:
            logger.error(f"Failed to add discount section: {e}")
            return html

    def _enhance_kfood_products(
        self,
        html: str,
        topic: str,
        mode: str,
    ) -> str:
        """Enhance K-Food content with dynamic product images from Amazon.

        Finds product-link divs and adds actual product images above them.

        Args:
            html: HTML content
            topic: Topic/product name
            mode: Blog mode

        Returns:
            HTML with product images added
        """
        if mode != "kculture":
            return html

        try:
            # Import ImageCrawler
            from src.image_crawler import ImageCrawler

            crawler = ImageCrawler(use_playwright=False)

            # Extract main product keywords from topic
            # Remove year and common words
            clean_topic = re.sub(r'\b(2025|2026|trends?|guide|review|best|top)\b', '', topic, flags=re.IGNORECASE)
            clean_topic = re.sub(r'[*_#]', '', clean_topic).strip()

            # Find product-link divs and extract product names
            product_link_pattern = r'<div class="product-link"[^>]*>.*?<strong>🛒 Buy ([^:]+):.*?</div>'
            matches = list(re.finditer(product_link_pattern, html, re.DOTALL))

            if not matches:
                # Try fetching images based on topic
                logger.debug(f"No product-link divs found, using topic: {clean_topic}")
                products = crawler.search_amazon_kfood_multiple(clean_topic, max_results=3)

                if products:
                    # Add a product showcase section before first H2
                    product_html = self._generate_product_showcase(products, clean_topic)
                    first_h2 = re.search(r'<h2[^>]*>', html)
                    if first_h2:
                        insert_pos = first_h2.start()
                        html = html[:insert_pos] + product_html + html[insert_pos:]
                        logger.info(f"Added product showcase with {len(products)} Amazon products")
                return html

            # Process each product-link div
            used_urls = set()
            for match in matches[:5]:  # Limit to 5 products
                product_name = match.group(1).strip()

                # Fetch product image
                product = crawler.search_amazon_kfood(product_name)

                if product and product.url and product.url not in used_urls:
                    used_urls.add(product.url)

                    # Create image HTML
                    img_html = f'''
<div class="product-image" style="text-align:center;margin:15px 0;">
  <img src="{product.url}" alt="{product.product_name[:60]}" style="max-width:300px;height:auto;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.1);" />
  <p style="font-size:12px;color:#666;margin-top:8px;">Image: Amazon</p>
</div>
'''
                    # Insert image before the product-link div
                    html = html[:match.start()] + img_html + html[match.start():]
                    logger.debug(f"Added product image for: {product_name[:30]}")

            return html

        except Exception as e:
            logger.warning(f"Failed to enhance K-Food products: {e}")
            return html

    def _generate_product_showcase(self, products: list, topic: str) -> str:
        """Generate a product showcase section from Amazon products.

        Args:
            products: List of CrawledImage objects
            topic: Topic for section title

        Returns:
            HTML for product showcase
        """
        if not products:
            return ""

        # Sanitize topic for URL - remove markdown, years, generic words
        clean_topic = re.sub(r'\*+', '', topic)  # Remove markdown asterisks
        clean_topic = re.sub(r'[#_~`]', '', clean_topic)  # Remove other markdown
        clean_topic = re.sub(r'\b(2025|2026|trends?|guide|review|best|top|ultimate)\b', '', clean_topic, flags=re.IGNORECASE)
        clean_topic = re.sub(r'\s+', ' ', clean_topic).strip()
        search_term = clean_topic.replace(' ', '+')

        product_items = ""
        for p in products[:4]:
            product_items += f'''
<div style="flex:1;min-width:200px;text-align:center;padding:15px;">
  <img src="{p.url}" alt="{p.product_name[:50]}" style="max-width:180px;height:auto;border-radius:8px;" />
  <p style="font-size:14px;margin:10px 0;font-weight:500;">{p.product_name[:40]}...</p>
  <a href="https://www.amazon.com/s?k={search_term}&i=grocery" target="_blank" rel="nofollow" style="color:#ff6d00;text-decoration:none;">View on Amazon →</a>
</div>
'''

        return f'''
<div class="product-showcase" style="background:#fffaf0;border-radius:12px;padding:20px;margin:25px 0;">
  <h3 style="text-align:center;color:#e65100;margin-bottom:20px;">🛒 Featured Products</h3>
  <div style="display:flex;flex-wrap:wrap;gap:15px;justify-content:center;">
    {product_items}
  </div>
  <p style="text-align:center;font-size:12px;color:#888;margin-top:15px;">Products from Amazon</p>
</div>
'''

    @staticmethod
    def convert_krw_to_usd(price_krw: int, exchange_rate: float = 1350.0) -> str:
        """Convert KRW price to USD with both values displayed.

        For US market readers who may not know KRW value.

        Args:
            price_krw: Price in Korean Won
            exchange_rate: KRW to USD rate (default: 1350)

        Returns:
            Formatted price string like "15,000 KRW (~$11 USD)"
        """
        usd = price_krw / exchange_rate
        krw_formatted = f"{price_krw:,}"

        if usd < 1:
            return f"{krw_formatted} KRW (~${usd:.2f} USD)"
        elif usd < 10:
            return f"{krw_formatted} KRW (~${usd:.1f} USD)"
        else:
            return f"{krw_formatted} KRW (~${int(round(usd))} USD)"

    @staticmethod
    def format_price_with_usd(text: str, exchange_rate: float = 1350.0) -> str:
        """Find KRW prices in text and add USD equivalent.

        Handles patterns like:
        - "15,000원" -> "15,000 KRW (~$11 USD)"
        - "15000 KRW" -> "15,000 KRW (~$11 USD)"
        - "₩15,000" -> "15,000 KRW (~$11 USD)"

        Args:
            text: Text containing KRW prices
            exchange_rate: KRW to USD rate (default: 1350)

        Returns:
            Text with USD equivalents added
        """
        def replace_price(match):
            # Extract the numeric part
            price_str = match.group(0)
            # Remove non-numeric characters except comma
            numeric_str = re.sub(r'[^\d,]', '', price_str)
            numeric_str = numeric_str.replace(',', '')

            if not numeric_str:
                return match.group(0)

            try:
                price_krw = int(numeric_str)
                if price_krw < 100:  # Too small, probably not a price
                    return match.group(0)

                usd = price_krw / exchange_rate
                krw_formatted = f"{price_krw:,}"

                if usd < 1:
                    return f"{krw_formatted} KRW (~${usd:.2f} USD)"
                elif usd < 10:
                    return f"{krw_formatted} KRW (~${usd:.1f} USD)"
                else:
                    return f"{krw_formatted} KRW (~${int(round(usd))} USD)"
            except ValueError:
                return match.group(0)

        # Pattern to match Korean Won prices
        # ₩15,000 / 15,000원 / 15000 KRW / 15,000 won
        pattern = r'(?:₩|원\s*)?[\d,]+(?:\s*(?:원|KRW|won|Won))?(?:\s*KRW)?'

        # Only replace if followed by currency indicator or at word boundary
        result = re.sub(
            r'(?:₩[\d,]+|[\d,]+\s*원|[\d,]+\s*KRW|[\d,]+\s*[Ww]on)',
            replace_price,
            text
        )
        return result

    def _validate(self, html: str) -> tuple[bool, list[str]]:
        """Validate generated content.

        Args:
            html: HTML content

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors: list[str] = []

        # Check word count
        word_count = self._count_words(html)
        if word_count < self.config.min_words:
            errors.append(f"Word count {word_count} below minimum {self.config.min_words}")

        # H1 check removed - WordPress adds H1 automatically from post title
        # Content should start with H2

        # Check for H2 sections (need at least 4)
        h2_count = len(re.findall(r"<h2[^>]*>", html, re.IGNORECASE))
        if h2_count < 4:
            errors.append(f"Only {h2_count} H2 headings, need at least 4")

        # Check for FAQ section (flexible pattern to catch variations)
        faq_patterns = [
            r"<h2[^>]*>.*?FAQ.*?</h2>",
            r"<h2[^>]*>.*?Frequently Asked.*?</h2>",
            r"<h2[^>]*>.*?Common Questions.*?</h2>",
            r"<h2[^>]*>.*?Q\s*&\s*A.*?</h2>",
            r"<h2[^>]*>.*?자주\s*묻는.*?</h2>",  # Korean FAQ
        ]
        has_faq = any(re.search(p, html, re.IGNORECASE | re.DOTALL) for p in faq_patterns)
        if not has_faq:
            errors.append("Missing FAQ section")

        # Check for source links (E-E-A-T requirement)
        # Count statistics that should have sources (percentages, numbers with context)
        stat_patterns = [
            r'\d+%',  # Percentages
            r'\$[\d,]+(?:\.\d{2})?(?:/month|/year)?',  # Prices
            r'[\d,]+\s*(?:stars|users|downloads|contributors)',  # Community metrics
            r'(?:response time|latency).*?[\d.]+\s*(?:ms|seconds?|s)\b',  # Performance
        ]

        total_stats = 0
        for pattern in stat_patterns:
            total_stats += len(re.findall(pattern, html, re.IGNORECASE))

        # Count source links (anchor tags with source-like text)
        source_links = len(re.findall(
            r'<a[^>]*href=["\'][^"\']+["\'][^>]*>.*?(?:source|Source|official|docs|GitHub|stackoverflow).*?</a>',
            html, re.IGNORECASE | re.DOTALL
        ))

        # Also count general external links as partial sources
        external_links = len(re.findall(r'<a[^>]*href=["\']https?://[^"\']+["\']', html, re.IGNORECASE))

        # Warn if too few source links for the number of statistics
        # Require at least 1 source link per 5 statistics, minimum 3 source links
        min_sources = max(3, total_stats // 5)
        if external_links < min_sources:
            errors.append(f"Insufficient source links: {external_links} links for {total_stats} statistics (need {min_sources}+)")

        # Check for sections longer than 300 words (Yoast readability requirement)
        long_sections = self._check_section_length(html, max_words=300)
        if long_sections:
            errors.append(f"Section too long (>300 words): {long_sections[0][:50]}...")

        is_valid = len(errors) == 0
        return is_valid, errors

    def _check_section_length(self, html: str, max_words: int = 300) -> list[str]:
        """Check for H2 sections that exceed max word count.

        Args:
            html: HTML content
            max_words: Maximum words allowed per H2 section

        Returns:
            List of section titles that exceed the limit
        """
        long_sections = []

        # Split content by H2 headings
        h2_pattern = r'<h2[^>]*>(.*?)</h2>'
        h2_matches = list(re.finditer(h2_pattern, html, re.IGNORECASE | re.DOTALL))

        for i, match in enumerate(h2_matches):
            section_title = re.sub(r'<[^>]+>', '', match.group(1)).strip()

            # Get content between this H2 and next H2 (or end)
            start_pos = match.end()
            if i + 1 < len(h2_matches):
                end_pos = h2_matches[i + 1].start()
            else:
                end_pos = len(html)

            section_content = html[start_pos:end_pos]

            # Check if section has H3 subheadings
            has_h3 = bool(re.search(r'<h3[^>]*>', section_content, re.IGNORECASE))

            # If no H3, count words in the entire section
            if not has_h3:
                # Remove HTML tags and count words
                text = re.sub(r'<[^>]+>', ' ', section_content)
                text = re.sub(r'\s+', ' ', text).strip()
                word_count = len(text.split())

                if word_count > max_words:
                    long_sections.append(f"{section_title} ({word_count} words)")

        return long_sections
