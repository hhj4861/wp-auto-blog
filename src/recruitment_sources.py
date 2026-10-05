"""Reject unrelated/explicitly expired hiring sources before spending plan slots.

This is acquisition filtering, not proof of an open vacancy or publication approval.
Unknown dates still need the existing independent topic and article reviewers.
"""
from datetime import date, datetime
import re
import unicodedata
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit


def compact(value):
    return re.sub(r"[^가-힣a-z0-9]", "", unicodedata.normalize("NFKC", value).lower())


def employer(keyword):
    key = compact(keyword)
    # Only organization-specific queries. General hiring guides retain their path.
    name, sep, _ = key.partition("채용")
    name = re.sub(r"^20\d{2}년?", "", name)
    name = re.sub(r"(?:(?:상반기|하반기|신입사원|경력사원|신입직원|신입|경력|생산직|인턴|공개|공채))+$", "", name)
    if not sep or len(name) < 2 or name in {"공기업", "공공기관", "공무원", "중소기업", "대기업", "장애인", "청년"}:
        return None
    return name


def source_issue(keyword, source, *, today=None):
    name = employer(keyword)
    if name is None or not isinstance(source, dict):
        return None
    text = source.get("excerpt", "")
    if not isinstance(text, str):
        return "missing_recruitment_body"
    body = compact(text)
    if name not in body:
        return "recruitment_employer_mismatch"
    details = ("응시자격", "지원자격", "전형절차", "전형방법", "접수기간", "접수마감", "채용기간", "모집분야")
    if not any(term in body for term in details):
        return "recruitment_detail_missing"
    # Require an explicit application deadline label. Employment periods, posting
    # dates and historical dates elsewhere in the body must not become deadlines.
    normalized = unicodedata.normalize("NFKC", text)
    token = r"(?:20\d{2}|\d{2})[.\-/]\s*\d{1,2}[.\-/]\s*\d{1,2}"
    ends = re.findall(r"접수\s*마감일\s*[:：]?\s*(" + token + r")", normalized)
    if urlsplit(source.get("url", "")).hostname == "job.alio.go.kr":
        # JOB-ALIO's metadata label means application period. Elsewhere the
        # same wording may mean employment/contract duration.
        metadata = normalized.split("등록일", 1)[0]
        ends += re.findall(r"채용기간\s*[:：]?\s*" + token + r"\s*~\s*(" + token + r")", metadata)
    dates = []
    for end in ends:
        year, month, day = (int(x) for x in re.findall(r"\d+", end))
        try:
            dates.append(date(year + 2000 if year < 100 else year, month, day))
        except ValueError:
            return "invalid_recruitment_deadline"
    # Conflicting/multiple deadlines are left to the semantic reviewer; never
    # infer that a document is current just because one date is in the future.
    clock = today or datetime.now(ZoneInfo("Asia/Seoul")).date()
    if dates and all(value < clock for value in dates):
        return "expired_recruitment_source"
    return None
