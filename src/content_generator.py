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
    """

    title: str
    html: str
    meta_description: str
    keywords: list[str]
    word_count: int
    content_type: ContentType

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "html": self.html,
            "meta_description": self.meta_description,
            "keywords": self.keywords,
            "word_count": self.word_count,
            "content_type": self.content_type.value,
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

[표(Table) 스타일] - 모던 다크테마 + 라운드 코너:
<table style="margin:0 auto 30px auto;border-collapse:separate;border-spacing:0;width:100%;max-width:800px;border-radius:12px;overflow:hidden;box-shadow:0 4px 15px rgba(0,0,0,0.2);">
<thead>
<tr style="background:#5046e5;">
<th style="padding:16px 20px;text-align:center;color:#fff;font-weight:600;font-size:0.95em;">항목</th>
<th style="padding:16px 20px;text-align:center;color:#fff;font-weight:600;font-size:0.95em;">설명</th>
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
※ 표 다음에는 반드시 30px 이상 여백 확보
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

=== 필수 구조 ===
※ 중요: 콘텐츠에 H1 태그 절대 사용 금지! (WordPress가 제목을 H1으로 자동 렌더링함)
※ 본문은 H2부터 시작

1. 제목 생성 (2단계 프로세스):

당신은 월간 조회수 100만 회 IT/경제 블로그의 '수석 편집장'이자 'SEO 마케팅 전문가'입니다.

[1단계] 아래 3가지 전략적 프레임으로 제목 후보 3개를 먼저 구상하세요:

**[효용 강조형]** 구체적 숫자(%, 금액, 년수)와 즉각적 이익 강조 (% 강조)
- 예: "지출 인식률 23% 상승! 복잡한 금융 앱 대신 '텍스트 파일' 하나로 끝내는 법"
- 예: "10년간 앱 없이 1억 모은 개발자의 가계부 비법"

**[트렌드 분석형]** 현재 시점(2026)과 최신 유행 키워드 반영
- 예: "2026년 재무 관리 트렌드: 왜 우리는 다시 '텍스트 가계부'로 돌아가는가?"
- 예: "2026년 디지털 미니멀리즘, 왜 개발자들은 앱을 버리나"

**[SEO/직관형]** 검색 사용자가 입력할 핵심 키워드 + 명확한 주제
- 예: "텍스트 파일 가계부 사용법 완벽 가이드"
- 예: "앱보다 강력한 메모장 가계부: 10년 가는 '텍스트 기반 재테크' 가이드"

[2단계] 3개 후보 중 가장 클릭율이 높을 것을 선택하고, 25-30자 이내로 압축하세요!
- 핵심 키워드만 남기고 수식어 제거
- 호기심 유발 요소 유지
- "와", "과", ":", "의" 등으로 끝나지 않게!

[최종 제목 예시] (20-30자)
✓ "Claude Code Skills 활용법" (22자)
✓ "개발자가 텍스트 파일로 1억 모은 비결" (20자)
✓ "2026 AI 코딩 어시스턴트 완전 정복" (20자)

※ 최종 출력: H1 태그 없이 압축된 제목 텍스트만!
※ 30자 초과 금지! 어색하게 잘리지 않는 자연스러운 제목!

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

=== TITLE OPTIMIZATION (SEO - MAX 60 CHARS!) ===
CRITICAL: Title MUST be under 60 characters for SEO!
Format: "[Tool A] vs [Tool B]: [Short Hook]"

GOOD (under 60 chars):
- "Vercel vs Netlify: 2026 Free Tier Showdown" (42 chars)
- "Linear vs Jira: Which Ships Faster?" (36 chars)

BAD (too long):
- "Linear vs Jira vs Asana: The 2026 Performance Benchmark (Who Wins?)" (68 chars)

Include: year (2026), power words (Showdown, Battle, Wins, Truth)

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

=== CONTENT QUALITY (Developers detect AI spam!) ===
- Real pros/cons - be HONEST about limitations
- Personal experience tone: "After using Linear for 6 months, I found..."
- Avoid generic fluff - every sentence must add value

=== STRICT RULES ===
- Write ONLY in English for US/UK/Global audience
- Use CURRENT YEAR (2026) - NEVER 2025 or older
- Be technically accurate - readers are EXPERTS
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

=== STRUCTURE (Order matters!) ===
1. H1: Click-worthy title with year and hook
2. TL;DR SUMMARY BOX (MUST come FIRST)
3. Quick Comparison Table
4. Deep Dive Sections (5-7 H2):
   - Pricing Breakdown (with table)
   - Performance & Speed
   - Key Features
   - Developer Experience
   - Migration Guide (if applicable)
5. Verdict Section (id="verdict")
6. CTA button (blue, links to real product URL)

=== IMPORTANT ===
- Use REAL product URLs for all buttons/CTAs (see list above)
- Add target="_blank" rel="noopener" to all external links
- Stick to blue/cyan color palette only
- No rainbow colors - professional, consistent look

Output: Clean HTML only, no markdown, no meta-commentary. Start directly with <h1>.
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

        # Generate content with LLM
        raw_html = self._call_llm(prompt)

        # Clean and process HTML
        html = self._clean_html(raw_html)

        # Extract title and remove H1 from content (WordPress adds H1 automatically)
        title = self._extract_title(html) or topic
        # 제목 길이 체크: tech 모드는 전체 제목 유지, general 모드만 30자로 축약
        if mode != "tech" and len(title) > 30:
            logger.warning(f"Title too long ({len(title)} chars): {title}")
            title = self._shorten_title(title, max_length=30)
        html = self._remove_h1(html)

        # Apply category-based color theme (H2, strong, boxes, etc.)
        html = self._apply_category_theme(html, category)

        # Generate meta description
        meta_description = self._generate_meta(topic, keywords, html)

        # Count words
        word_count = self._count_words(html)

        # Validate content
        is_valid, errors = self._validate(html)
        if not is_valid:
            logger.warning(f"Content validation warnings: {errors}")

        return GeneratedContent(
            title=title,
            html=html,
            meta_description=meta_description,
            keywords=keywords,
            word_count=word_count,
            content_type=content_type,
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

    def _shorten_title(self, title: str, max_length: int = 50) -> str:
        """Shorten title to fit in one line.

        Args:
            title: Original title
            max_length: Maximum character length (default 50 for English, 30 for Korean)

        Returns:
            Shortened title
        """
        if len(title) <= max_length:
            return title

        # VS comparison pattern: keep "A vs B vs C" part intact
        # e.g., "Linear vs Jira vs Asana APIs in 2026: The Developer..." -> "Linear vs Jira vs Asana"
        vs_pattern = re.search(r'^([A-Za-z0-9\s]+(?:\s+vs\s+[A-Za-z0-9\s]+)+)', title, re.IGNORECASE)
        if vs_pattern:
            vs_part = vs_pattern.group(1).strip()
            # Clean up trailing words like "APIs", "in", "2026"
            vs_part = re.sub(r'\s+(APIs?|in|for|with|\d{4}).*$', '', vs_part, flags=re.IGNORECASE)
            if 10 <= len(vs_part) <= max_length:
                logger.info(f"Title shortened (VS pattern): '{title}' -> '{vs_part}'")
                return vs_part

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

        # Check for FAQ section
        if not re.search(r"<h2[^>]*>\s*FAQ", html, re.IGNORECASE):
            errors.append("Missing FAQ section")

        is_valid = len(errors) == 0
        return is_valid, errors
