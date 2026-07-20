#!/usr/bin/env python3
"""trendpulse.blog 정비 스크립트 (2026-07 감사 후속 퀵윈).

수행 작업:
  1. 사이트 타이틀/태그라인 설정, 신규 글 댓글 기본값 닫기
  2. 작성자 표시명/슬러그에서 Gmail 노출 제거
  3. 필수 페이지 생성/발행: 개인정보처리방침 / 소개 / 문의 (+메뉴 링크 시도)
  4. 스팸 댓글(외부 링크 포함) 일괄 영구 삭제 — WP batch API 사용
  5. 포스트 정비:
     - 영문 제목(HN 잔존) → draft 전환
     - 제목의 LLM 메타 잔존물(백틱, "(37자)", "(유형 N)" 등) 자동 정정
     - 본문의 ((...)) 인용 플레이스홀더 제거
     - 전체 포스트 댓글 닫기
  6. __trashed 잔존 슬러그 완전 삭제
  7. 정크 태그 삭제 (0카운트 전체 + 저사용 영문 토큰)

DRY_RUN=true 면 변경 없이 대상만 보고한다.
GitHub Actions에서 WP_GENERAL_* 시크릿으로 실행하는 것을 전제로 한다.
"""

import os
import re
import time

import requests

BASE_URL = (os.environ.get("WP_GENERAL_URL") or os.environ.get("WP_URL") or "").rstrip("/")
USERNAME = os.environ.get("WP_GENERAL_USERNAME") or os.environ.get("WP_USERNAME") or ""
APP_PASSWORD = os.environ.get("WP_GENERAL_APP_PASSWORD") or os.environ.get("WP_APP_PASSWORD") or ""
DRY_RUN = (os.environ.get("DRY_RUN", "true").lower() != "false")

API = f"{BASE_URL}/wp-json/wp/v2"

SITE_TITLE = "TrendPulse"
SITE_TAGLINE = "IT·생산성·생활 정보를 한눈에 정리하는 트렌드 블로그"
AUTHOR_DISPLAY_NAME = "TrendPulse 에디터"
AUTHOR_SLUG = "trendpulse-editor"

# draft 전환 안전 상한 (영문 제목 잔존분 ~40-60건 예상)
MAX_DRAFTS = 80

HANGUL_RE = re.compile(r"[가-힣]")
TRASHED_SLUG_RE = re.compile(r"^_*trashed(-\d+)?$")
PAREN_PLACEHOLDER_RE = re.compile(r"\s*\(\([^()\n]{2,60}\)\)")

TAG_WHITELIST = {
    "ai", "api", "seo", "saas", "llm", "gpt", "chatgpt", "claude", "gemini",
    "python", "react", "wordpress", "adsense", "notion", "figma", "slack",
}

session = requests.Session()
session.auth = (USERNAME, APP_PASSWORD)
session.headers.update({"User-Agent": "Mozilla/5.0 (trendpulse-maintenance)"})

report = {}


def log(msg):
    print(msg, flush=True)


def req(method, path, *, params=None, json_body=None, attempt=0):
    url = path if path.startswith("http") else f"{API}{path}"
    try:
        r = session.request(method, url, params=params, json=json_body, timeout=60)
    except requests.RequestException as e:
        if attempt < 3:
            time.sleep(8 * (attempt + 1))
            return req(method, path, params=params, json_body=json_body, attempt=attempt + 1)
        raise SystemExit(f"요청 실패(재시도 소진): {method} {url}: {e}")
    if r.status_code in (403, 429, 502, 503, 504) and attempt < 3:
        # Hostinger WAF/레이트리밋 대응 백오프
        time.sleep(10 * (attempt + 1))
        return req(method, path, params=params, json_body=json_body, attempt=attempt + 1)
    return r


def paginate(path, params=None):
    params = dict(params or {})
    params.setdefault("per_page", 100)
    page = 1
    while True:
        params["page"] = page
        r = req("GET", path, params=params)
        if r.status_code == 400:  # 페이지 범위 초과
            return
        r.raise_for_status()
        items = r.json()
        if not items:
            return
        yield from items
        total_pages = int(r.headers.get("X-WP-TotalPages", "1"))
        if page >= total_pages:
            return
        page += 1


def write(method, path, json_body, ok_codes=(200, 201)):
    """DRY_RUN이면 실행하지 않는다."""
    if DRY_RUN:
        return None
    r = req(method, path, json_body=json_body)
    if r.status_code not in ok_codes:
        log(f"  ⚠️ {method} {path} → {r.status_code}: {r.text[:200]}")
        return None
    time.sleep(0.2)
    return r.json()


# ---------------------------------------------------------------- 페이지 본문

PRIVACY_HTML = """
<p><strong>시행일: 2026년 7월 20일</strong></p>
<p>TrendPulse(https://trendpulse.blog, 이하 &lsquo;본 사이트&rsquo;)는 방문자의 개인정보를 소중히 여기며, 관련 법령을 준수합니다. 본 방침은 본 사이트가 어떤 정보를 수집하고 어떻게 이용하는지 설명합니다.</p>
<h2>1. 수집하는 정보</h2>
<p>본 사이트는 회원 가입 없이 이용할 수 있으며, 이름·연락처 등 개인 식별 정보를 직접 수집하지 않습니다. 다만 서비스 운영 과정에서 다음 정보가 자동으로 수집될 수 있습니다.</p>
<ul>
<li>접속 기록: 브라우저 종류, 운영체제, 방문 일시, 유입 경로 등 (호스팅 서버 로그)</li>
<li>쿠키: 사이트 이용 통계 및 광고 게재를 위한 쿠키 (아래 2·3항 참조)</li>
</ul>
<h2>2. Google 애드센스 광고</h2>
<p>본 사이트는 Google 애드센스(Google AdSense) 광고를 게재합니다. Google을 포함한 제3자 광고 사업자는 쿠키를 사용하여 방문자의 이전 방문 기록을 바탕으로 맞춤형 광고를 표시할 수 있습니다.</p>
<ul>
<li>Google의 광고 쿠키 사용에 대한 자세한 내용은 <a href="https://policies.google.com/technologies/ads?hl=ko" target="_blank" rel="noopener">Google 광고 정책</a>에서 확인할 수 있습니다.</li>
<li>맞춤형 광고를 원하지 않는 경우 <a href="https://adssettings.google.com/" target="_blank" rel="noopener">Google 광고 설정</a>에서 언제든지 해제할 수 있습니다.</li>
<li><a href="https://optout.aboutads.info/" target="_blank" rel="noopener">www.aboutads.info</a>를 방문하여 제3자 광고 사업자의 맞춤형 광고 쿠키를 일괄 거부할 수도 있습니다.</li>
</ul>
<h2>3. 웹 분석 도구</h2>
<p>본 사이트는 서비스 개선을 위해 Google 애널리틱스(Google Analytics)를 사용합니다. Google 애널리틱스는 쿠키를 통해 익명화된 방문 통계(방문 페이지, 체류 시간 등)를 수집하며, 개인을 식별하는 정보는 수집하지 않습니다.</p>
<h2>4. 쿠키 관리 방법</h2>
<p>방문자는 웹 브라우저 설정을 통해 쿠키 저장을 거부하거나 저장된 쿠키를 삭제할 수 있습니다. 다만 쿠키를 차단할 경우 일부 서비스 이용에 제한이 있을 수 있습니다.</p>
<ul>
<li>Chrome: 설정 &rarr; 개인 정보 보호 및 보안 &rarr; 쿠키 및 기타 사이트 데이터</li>
<li>Safari: 환경설정 &rarr; 개인 정보 보호</li>
<li>Edge: 설정 &rarr; 쿠키 및 사이트 권한</li>
</ul>
<h2>5. 외부 링크</h2>
<p>본 사이트의 게시물에는 외부 사이트로 연결되는 링크가 포함될 수 있습니다. 외부 사이트의 개인정보 처리에 대해서는 본 방침이 적용되지 않으므로 해당 사이트의 방침을 확인하시기 바랍니다.</p>
<h2>6. 방침 변경</h2>
<p>본 방침은 법령 또는 서비스 변경에 따라 개정될 수 있으며, 개정 시 본 페이지를 통해 공지합니다.</p>
<h2>7. 문의</h2>
<p>개인정보 처리와 관련한 문의는 <a href="/contact/">문의 페이지</a>를 통해 연락해 주시기 바랍니다.</p>
"""

ABOUT_HTML = """
<p><strong>TrendPulse</strong>는 빠르게 변하는 IT·생산성·비즈니스 트렌드와 일상에 도움이 되는 생활 정보를 한눈에 볼 수 있도록 정리하는 블로그입니다.</p>
<h2>다루는 주제</h2>
<ul>
<li><strong>테크</strong> — AI 도구, 소프트웨어, 새로운 기술 흐름을 쉽게 풀어 소개합니다.</li>
<li><strong>생산성</strong> — 업무와 일상을 효율적으로 만드는 도구와 방법을 다룹니다.</li>
<li><strong>비즈니스</strong> — 일하는 사람에게 필요한 시장·산업 이야기를 정리합니다.</li>
<li><strong>생활 정보</strong> — 알아두면 도움이 되는 제도, 신청 방법, 실용 팁을 안내합니다.</li>
</ul>
<h2>콘텐츠 원칙</h2>
<ul>
<li>공식 출처(정부·기관·제조사 발표)를 우선 확인하고 출처를 표기합니다.</li>
<li>제도·수치가 바뀌면 글을 갱신하거나 갱신 시점을 명시합니다.</li>
<li>읽는 사람이 바로 행동할 수 있도록 신청 방법·확인 방법 중심으로 정리합니다.</li>
</ul>
<p>잘못된 정보를 발견하셨거나 다뤄줬으면 하는 주제가 있다면 <a href="/contact/">문의 페이지</a>로 알려주세요. 빠르게 확인하고 반영하겠습니다.</p>
"""

CONTACT_HTML = """
<p>TrendPulse에 관심 가져주셔서 감사합니다. 아래 연락처로 문의를 보내주시면 확인 후 답변드리겠습니다.</p>
<h2>이메일 문의</h2>
<p>📧 <a href="mailto:guswhd1085@gmail.com">guswhd1085@gmail.com</a></p>
<ul>
<li>콘텐츠 오류 제보 / 주제 제안</li>
<li>제휴 및 광고 문의</li>
<li>저작권 관련 문의</li>
</ul>
<p>보통 영업일 기준 2~3일 이내에 답변드립니다.</p>
<p>개인정보 처리에 대한 내용은 <a href="/privacy-policy/">개인정보처리방침</a>을 참고해 주세요.</p>
"""

PAGES = [
    {"slug": "privacy-policy", "title": "개인정보처리방침", "content": PRIVACY_HTML},
    {"slug": "about", "title": "소개", "content": ABOUT_HTML},
    {"slug": "contact", "title": "문의", "content": CONTACT_HTML},
]


# ---------------------------------------------------------------- 제목/본문 정정

def clean_title(title):
    """LLM 메타 출력 잔존물 제거: 백틱, "(37자)", "(유형 N ...)", 끝의 따옴표/별표."""
    s = title.strip()
    s = re.sub(r"[\s\"*]*\((?:유형\s*\d|[0-9]+\s*자)[^)]*\)", "", s)   # (유형 3), (37자), (유형 1 · 31자)
    s = re.sub(r"[\s\"*]*\[유형[^\]]*\]?", "", s)
    s = re.sub(r"[\s\"*]*\((?:유형\s*\d|[0-9]+\s*자)[^)]*$", "", s)    # 닫는 괄호 없이 잘린 경우
    s = s.strip().strip("`").strip()
    s = re.sub(r'["*\s]+$', "", s)
    s = re.sub(r'^["\s]+', "", s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s


def clean_content(content):
    """((Sleep 2024)) 류의 인용 플레이스홀더 제거."""
    cleaned = PAREN_PLACEHOLDER_RE.sub("", content)
    if cleaned != content:
        cleaned = re.sub(r"(?<=[가-힣\w.,]) {2,}(?=[가-힣\w])", " ", cleaned)
    return cleaned


# ---------------------------------------------------------------- 작업 단계

def task_auth_check():
    r = req("GET", "/users/me", params={"context": "edit"})
    if r.status_code != 200:
        raise SystemExit(f"인증 실패: {r.status_code} {r.text[:200]}")
    me = r.json()
    log(f"✅ 인증 OK: user id={me['id']}, slug={me.get('slug')!r}")
    return me


def task_settings():
    r = req("GET", "/settings")
    r.raise_for_status()
    cur = r.json()
    changes = {}
    if cur.get("title", "").strip() in ("", "trendpulse.blog"):
        changes["title"] = SITE_TITLE
    if not cur.get("description", "").strip():
        changes["description"] = SITE_TAGLINE
    if cur.get("default_comment_status") != "closed":
        changes["default_comment_status"] = "closed"
    report["settings"] = changes
    if changes:
        log(f"[설정] 변경 예정: {changes}")
        write("POST", "/settings", changes)
    else:
        log("[설정] 변경 사항 없음")


def task_author(me):
    changes = {}
    if "@" in me.get("name", "") or "gmail" in me.get("name", "").lower():
        changes["name"] = AUTHOR_DISPLAY_NAME
        changes["nickname"] = AUTHOR_DISPLAY_NAME
    if "gmail" in me.get("slug", "").lower():
        changes["slug"] = AUTHOR_SLUG
    report["author"] = changes
    if changes:
        log(f"[작성자] 변경 예정: {changes}")
        write("POST", f"/users/{me['id']}", changes)
    else:
        log("[작성자] 변경 사항 없음")


def task_pages():
    created, published, page_ids = [], [], {}
    for page in PAGES:
        r = req("GET", "/pages", params={"slug": page["slug"], "status": "any", "context": "edit"})
        existing = r.json() if r.status_code == 200 else []
        if existing:
            ex = existing[0]
            page_ids[page["slug"]] = ex["id"]
            if ex.get("status") == "publish":
                log(f"[페이지] /{page['slug']}/ 이미 발행됨 → 건너뜀")
                continue
            # WP 기본 생성 draft(예: 개인정보처리방침 샘플) → 본문 교체 후 발행
            log(f"[페이지] /{page['slug']}/ {ex.get('status')} 상태로 존재 → 본문 교체 + 발행")
            published.append(page["slug"])
            write("POST", f"/pages/{ex['id']}", {
                "title": page["title"],
                "content": page["content"].strip(),
                "status": "publish",
                "comment_status": "closed",
                "ping_status": "closed",
            })
        else:
            log(f"[페이지] 생성 예정: /{page['slug']}/ ({page['title']})")
            created.append(page["slug"])
            res = write("POST", "/pages", {
                "slug": page["slug"],
                "title": page["title"],
                "content": page["content"].strip(),
                "status": "publish",
                "comment_status": "closed",
                "ping_status": "closed",
            })
            if res:
                page_ids[page["slug"]] = res["id"]
    report["pages"] = {"created": created, "published": published}
    return page_ids


def _is_spam_comment(c):
    author_url = (c.get("author_url") or "").strip()
    content = c.get("content", {}).get("rendered", "")
    if author_url and "trendpulse.blog" not in author_url:
        return "외부 author_url"
    if re.search(r'<a\s[^>]*href="https?://(?!trendpulse\.blog)', content):
        return "본문 내 외부 링크"
    if re.search(r"https?://[^\s\"<]+", content):
        return "본문 내 URL"
    if re.search(r"\[url=", content, re.I):
        return "BBCode 링크"
    if re.search(r"[А-Яа-яЁё]", content):
        return "키릴 문자 스팸"
    if re.search(r"xevil|captcha", content, re.I):
        return "캡차 봇 스팸"
    return None


def task_comments():
    spam_ids, ham = [], []
    total = 0
    for status in ("approve", "hold"):
        for c in paginate("/comments", params={"status": status,
                                               "_fields": "id,author_url,content,author_name"}):
            total += 1
            if _is_spam_comment(c):
                spam_ids.append(c["id"])
            else:
                preview = re.sub(r"<[^>]+>", "", c["content"]["rendered"])[:60]
                ham.append((c["id"], c.get("author_name", ""), preview))

    log(f"[댓글] 전체 {total}건 중 스팸 {len(spam_ids)}건 영구 삭제 예정, 유지 {len(ham)}건")
    for cid, name, preview in ham[:100]:
        log(f"  - 유지: #{cid} {name!r} {preview!r}")
    if DRY_RUN:
        report["comments"] = {"total": total, "spam": len(spam_ids), "ham": len(ham)}
        return

    deleted = 0
    for i in range(0, len(spam_ids), 25):
        chunk = spam_ids[i:i + 25]
        r = req("POST", f"{BASE_URL}/wp-json/batch/v1", json_body={
            "requests": [{"method": "DELETE", "path": f"/wp/v2/comments/{cid}?force=true"}
                         for cid in chunk],
        })
        if r.status_code == 200:
            deleted += sum(1 for resp in r.json().get("responses", [])
                           if resp and resp.get("status") in (200, 410))
        else:
            log(f"  ⚠️ batch 삭제 실패({r.status_code}) — 개별 삭제로 폴백")
            for cid in chunk:
                req("DELETE", f"/comments/{cid}", params={"force": "true"})
                deleted += 1
        if deleted and deleted % 2500 < 25:
            log(f"  ... {deleted}/{len(spam_ids)} 삭제")
        time.sleep(0.15)
    log(f"[댓글] 삭제 완료: {deleted}건")
    report["comments"] = {"total": total, "spam_deleted": deleted, "ham": len(ham)}


def task_posts():
    drafts, title_fixes, content_fixes, comment_closes = [], [], [], 0
    for p in paginate("/posts", params={"context": "edit", "status": "publish",
                                        "_fields": "id,slug,title,content,comment_status"}):
        title_raw = p["title"].get("raw") or re.sub(r"<[^>]+>", "", p["title"].get("rendered", ""))
        content_raw = p["content"].get("raw") or p["content"].get("rendered", "")

        if not HANGUL_RE.search(title_raw):
            drafts.append((p["id"], title_raw[:70]))
            continue

        fixes = {}
        cleaned = clean_title(title_raw)
        if cleaned and cleaned != title_raw:
            fixes["title"] = cleaned
            fixes["meta"] = {"_yoast_wpseo_title": f"{cleaned} | {SITE_TITLE}"}
            title_fixes.append((p["id"], title_raw[:60], cleaned[:60]))
        new_content = clean_content(content_raw)
        if new_content != content_raw:
            fixes["content"] = new_content
            content_fixes.append(p["id"])
        if p.get("comment_status") == "open":
            fixes["comment_status"] = "closed"
            comment_closes += 1
        if fixes:
            if not DRY_RUN:
                write("POST", f"/posts/{p['id']}", fixes)

    log(f"[포스트] draft {len(drafts)}건 / 제목 정정 {len(title_fixes)}건 / "
        f"플레이스홀더 제거 {len(content_fixes)}건 / 댓글 닫기 {comment_closes}건")
    for pid, title in drafts:
        log(f"  - draft: #{pid} {title}")
    for pid, before, after in title_fixes[:60]:
        log(f"  - 제목: #{pid} {before!r} → {after!r}")

    if len(drafts) > MAX_DRAFTS:
        log(f"  ⚠️ draft 대상이 상한({MAX_DRAFTS}) 초과 — 규칙 오류 가능성. draft 전환 중단.")
        report["posts"] = {"drafts_planned": len(drafts), "aborted": True}
        return
    for pid, _ in drafts:
        write("POST", f"/posts/{pid}", {"status": "draft", "comment_status": "closed"})
    report["posts"] = {"drafted": len(drafts), "title_fixed": len(title_fixes),
                       "content_fixed": len(content_fixes), "comments_closed": comment_closes}


def task_trashed_slugs():
    victims = []
    for kind in ("pages", "posts"):
        r = req("GET", f"/{kind}", params={"search": "trashed", "status": "any",
                                           "context": "edit", "per_page": 50})
        if r.status_code != 200:
            continue
        for item in r.json():
            if TRASHED_SLUG_RE.match(item.get("slug", "")):
                victims.append((kind, item["id"], item["slug"]))
    log(f"[__trashed] 완전 삭제 대상 {len(victims)}건: {[v[2] for v in victims]}")
    for kind, pid, slug in victims:
        if not DRY_RUN:
            req("DELETE", f"/{kind}/{pid}", params={"force": "true"})
    report["trashed_slugs"] = [v[2] for v in victims]


def task_tags():
    junk = []
    for t in paginate("/tags", params={"orderby": "count", "order": "asc"}):
        name = t.get("name", "")
        count = t.get("count", 99)
        if count == 0:
            junk.append((t["id"], name, count))
        elif (re.fullmatch(r"[a-z]{3,15}", name)
                and name.lower() not in TAG_WHITELIST
                and count <= 3):
            junk.append((t["id"], name, count))
    log(f"[태그] 정크 태그 삭제 대상 {len(junk)}건 (0카운트 + 저사용 영문 토큰)")
    for tid, name, count in junk[:60]:
        log(f"  - tag #{tid} {name!r} (글 {count}개)")
    if len(junk) > 60:
        log(f"  ... 외 {len(junk) - 60}건")
    if not DRY_RUN:
        for i in range(0, len(junk), 25):
            chunk = junk[i:i + 25]
            req("POST", f"{BASE_URL}/wp-json/batch/v1", json_body={
                "requests": [{"method": "DELETE", "path": f"/wp/v2/tags/{tid}?force=true"}
                             for tid, _, _ in chunk],
            })
            time.sleep(0.15)
    report["tags_deleted"] = len(junk)


def task_nav_links(page_ids):
    """필수 페이지 링크 노출: 푸터 위젯 → 메뉴 순으로 시도."""
    r = req("GET", "/sidebars")
    footer = None
    if r.status_code == 200:
        footer = next((s for s in r.json() if "footer" in s.get("id", "").lower()
                       or "footer" in (s.get("name") or "").lower()), None)
    if footer:
        wr = req("GET", "/widgets", params={"sidebar": footer["id"]})
        if wr.status_code == 200 and any("privacy-policy" in (w.get("rendered") or "")
                                         for w in wr.json()):
            log("[링크] 푸터 링크 위젯 이미 존재")
            report["nav_links"] = "exists"
            return
        html = ('<p style="text-align:center"><a href="/about/">소개</a> · '
                '<a href="/privacy-policy/">개인정보처리방침</a> · '
                '<a href="/contact/">문의</a></p>')
        log(f"[링크] 푸터({footer['id']})에 필수 페이지 링크 위젯 추가 예정")
        write("POST", "/widgets", {
            "id_base": "custom_html",
            "sidebar": footer["id"],
            "instance": {"raw": {"title": "", "content": html}},
        })
        report["nav_links"] = f"footer:{footer['id']}"
        return

    mr = req("GET", "/menus")
    menus = mr.json() if mr.status_code == 200 else []
    # 실제 테마 위치에 연결된 메뉴를 우선 사용
    lr = req("GET", "/menu-locations")
    if lr.status_code == 200:
        assigned = [loc.get("menu") for loc in lr.json().values() if loc.get("menu")]
        if assigned:
            menus = sorted(menus, key=lambda m: m["id"] not in assigned)
    if not menus:
        log("[링크] 푸터 위젯/메뉴 모두 없음 → 관리자 화면에서 수동 추가 필요 "
            "(외모 > 메뉴 또는 위젯에 소개/개인정보처리방침/문의 링크)")
        report["nav_links"] = "manual"
        return
    menu_id = menus[0]["id"]
    existing = req("GET", "/menu-items", params={"menus": menu_id, "per_page": 100})
    existing_objects = {i.get("object_id") for i in existing.json()} if existing.status_code == 200 else set()
    added = []
    for slug in ("about", "privacy-policy", "contact"):
        pid = page_ids.get(slug)
        if not pid or pid in existing_objects:
            continue
        title = next(p["title"] for p in PAGES if p["slug"] == slug)
        log(f"[링크] 메뉴({menus[0].get('name')})에 {title} 추가 예정")
        added.append(slug)
        write("POST", "/menu-items", {
            "title": title, "menus": menu_id, "type": "post_type",
            "object": "page", "object_id": pid, "status": "publish",
        })
    report["nav_links"] = {"menu": menu_id, "added": added}


def main():
    if not BASE_URL or not USERNAME or not APP_PASSWORD:
        raise SystemExit("WP_GENERAL_URL / WP_GENERAL_USERNAME / WP_GENERAL_APP_PASSWORD 필요")
    if "trendpulse" not in BASE_URL:
        raise SystemExit(f"안전장치: 대상이 trendpulse가 아님 ({BASE_URL}) — 중단")

    log(f"{'=' * 60}\n대상: {BASE_URL} | DRY_RUN={DRY_RUN}\n{'=' * 60}")
    me = task_auth_check()
    task_settings()
    task_author(me)
    page_ids = task_pages()
    task_comments()
    task_posts()
    task_trashed_slugs()
    task_tags()
    task_nav_links(page_ids)

    log(f"\n{'=' * 60}\n요약: {report}")
    if DRY_RUN:
        log("DRY_RUN 모드였음 — 실제 변경 없음. 적용하려면 DRY_RUN=false로 재실행.")


if __name__ == "__main__":
    main()
