#!/usr/bin/env python3
"""commerce-automation-kit(keyword-intel) → wp-auto-blog 단방향 export 브릿지 소비자.

설계 근거: commerce-automation-kit/packages/keyword-intel/docs/QUESTION-MINING.md §8
및 wp-auto-blog/architecture/modules/03-question-mining-search.md.

두 저장소는 서로 다른 법체계/컴플라이언스다 — 코드·저장·게이트 통합 금지.
연결은 **단방향 JSON export 계약**만 (kit 생산 → 블로그 소비).

거버넌스 의무 (코드로 강제):
  - schemaVersion·compliance(resaleRestricted,cacheTtlHours) 필수·타입검증, 위반 시 거부.
  - **보수모드 상시**: 질문 원문(source_questions)은 큐에 절대 저장하지 않는다.
    파이프라인(run_single)이 topic/keywords/category만 소비하므로 원문 저장은
    기능적 이득 0 · 컴플라이언스 부채만 남는다. §8 "재표현 게이트"를 저장 배제로 강제.
    (verbatim/FAQ 주입은 전용 소비자 + 하드TTL 저장소가 생길 때 별도 설계 — 현재 범위 밖)
  - **항목 삭제 없음**: TTL은 legacy source_questions '필드'만 제거하고 topic 등
    가공물은 보존한다(§8 "topic 등 가공물은 유지"). cak 항목을 통째로 지우지 않는다.
  - dedup(재작성 안 함): 여기서는 정규화 토픽 비교로 큐 중복만 거른다(completed·pending 모두).
    하드 게이트(_is_duplicate)와 keyword_gate.evaluate() 재통과는 발행 시 파이프라인이 수행.

이 스크립트는 export 파일이 있고 수동 실행할 때만 동작한다 — 자동 발행
파이프라인(auto-post.yml)엔 배선하지 않는다(발행 동작 변화 없음).

사용법:
    python scripts/ingest_keyword_intel.py <export.json>
    CAK_KEYWORD_INTEL_EXPORT=/path/export.json python scripts/ingest_keyword_intel.py
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path

SUPPORTED_SCHEMA_VERSIONS = {1}
QUEUE_SOURCE = "cak_keyword_intel"
QUEUE_PATH = Path(__file__).parent.parent / "data" / "topic_queue_general.json"


class IngestError(Exception):
    """export/큐 계약 위반 — 조용히 넘기지 않고 실패시킨다."""


def validate_export(export: dict) -> None:
    """schemaVersion·compliance 필수·타입 검증 (§10: compliance 필드 필수 포함)."""
    if not isinstance(export, dict):
        raise IngestError("export 최상위는 object여야 함")
    ver = export.get("schemaVersion")
    if ver not in SUPPORTED_SCHEMA_VERSIONS:
        raise IngestError(
            f"지원하지 않는 schemaVersion: {ver!r} (지원: {sorted(SUPPORTED_SCHEMA_VERSIONS)})"
        )
    comp = export.get("compliance")
    if not isinstance(comp, dict):
        raise IngestError("compliance 필드 누락 — 단방향 계약은 compliance 필수")
    if "resaleRestricted" not in comp:
        raise IngestError("compliance.resaleRestricted 누락")
    ttl = comp.get("cacheTtlHours")
    if not isinstance(ttl, int) or isinstance(ttl, bool) or ttl <= 0:
        raise IngestError(
            f"compliance.cacheTtlHours 는 양의 정수여야 함 (받음: {ttl!r})"
        )


def _parse_iso(ts: str) -> _dt.datetime:
    """naive/aware ISO 모두 naive UTC 기준으로 파싱 (오프셋 있으면 UTC로 환산)."""
    s = str(ts).strip().replace("Z", "+00:00")
    try:
        dt = _dt.datetime.fromisoformat(s)
    except ValueError:
        # 오프셋/마이크로초 이형 방어: 앞 19자(YYYY-MM-DDTHH:MM:SS)만
        dt = _dt.datetime.fromisoformat(s[:19])
    if dt.tzinfo is not None:
        dt = (dt - dt.utcoffset()).replace(tzinfo=None)
    return dt


def purge_stale_questions(queue: list, now: str, ttl_hours: int) -> tuple[list, int]:
    """TTL 경과한 cak 항목의 source_questions '필드'만 제거하고 항목은 보존한다.

    §8: "TTL 경과 시 source_questions 필드 purge (topic 등 가공물은 유지)".
    항목을 통째로 삭제하지 않는다. 네이티브(블로그 자체) 항목은 불가침.
    (보수모드 상시로 신규 항목엔 source_questions가 없으므로, 이건 legacy 안전망이다.)
    """
    now_dt = _parse_iso(now)
    purged = 0
    for item in queue:
        if item.get("source") != QUEUE_SOURCE or "source_questions" not in item:
            continue
        ing = item.get("ingested_at")
        if not ing:
            continue
        age_h = (now_dt - _parse_iso(ing)).total_seconds() / 3600
        if age_h > ttl_hours:
            item.pop("source_questions", None)
            purged += 1
    return queue, purged


def _normalize(topic: str) -> str:
    return re.sub(r"\s+", " ", str(topic or "").strip().lower())


def build_queue_item(item: dict, now: str) -> dict:
    """export 항목 → 큐 pending 항목. 질문 원문은 절대 싣지 않는다(보수모드 상시)."""
    out = {
        "topic": item["topic"],
        "keywords": list(item.get("keywords") or []),
        "category": item.get("category", ""),
        "status": "pending",
        "source": QUEUE_SOURCE,
        "ingested_at": now,
    }
    if item.get("monthly_search") is not None:
        out["monthly_search"] = item["monthly_search"]
    if item.get("opportunity") is not None:
        out["opportunity"] = item["opportunity"]
    return out


def ingest(export: dict, queue: list, now: str) -> tuple[list, dict]:
    """export를 큐에 병합한다. (새 큐, 요약) 반환."""
    validate_export(export)
    if not isinstance(queue, list):
        raise IngestError(f"큐는 list여야 함 (받음: {type(queue).__name__})")
    ttl = int(export["compliance"]["cacheTtlHours"])

    queue, purged = purge_stale_questions(queue, now=now, ttl_hours=ttl)
    seen = {_normalize(q.get("topic", "")) for q in queue}

    added = skipped = 0
    for raw in export.get("items", []):
        topic = raw.get("topic")
        if not isinstance(topic, str) or not topic.strip():
            skipped += 1  # null·숫자·빈문자 등 — 배치 전체를 죽이지 않고 스킵
            continue
        key = _normalize(topic)
        if key in seen:
            skipped += 1
            continue
        queue.append(build_queue_item({**raw, "topic": topic.strip()}, now=now))
        seen.add(key)
        added += 1

    return queue, {"added": added, "skipped_dup": skipped, "questions_purged": purged}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", nargs="?", default=os.environ.get("CAK_KEYWORD_INTEL_EXPORT"),
                        help="keyword-intel export JSON 경로")
    parser.add_argument("--queue", default=str(QUEUE_PATH), help="대상 큐 파일")
    args = parser.parse_args()

    if not args.export:
        print("ERROR: export 경로가 필요합니다 (인자 또는 CAK_KEYWORD_INTEL_EXPORT)")
        return 2
    export_path = Path(args.export)
    if not export_path.exists():
        print(f"ERROR: export 파일 없음: {export_path}")
        return 2

    try:
        export = json.loads(export_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"거부(export JSON 파싱 실패): {e}")
        return 1

    queue_path = Path(args.queue)
    queue = []
    if queue_path.exists():
        try:
            queue = json.loads(queue_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"ERROR: 큐 JSON 파싱 실패: {e}")
            return 1

    now = _dt.datetime.now().isoformat()
    try:
        new_queue, summary = ingest(export, queue, now=now)
    except IngestError as e:
        print(f"거부(계약 위반): {e}")
        return 1

    queue_path.write_text(
        json.dumps(new_queue, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"ingest 완료 — 추가 {summary['added']} / 중복스킵 {summary['skipped_dup']} "
        f"/ legacy질문TTL제거 {summary['questions_purged']} (큐={queue_path.name})"
    )
    print("→ 발행: python -m src.main --mode general --from-queue "
          "(dedup·keyword_gate 재통과 자동)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
