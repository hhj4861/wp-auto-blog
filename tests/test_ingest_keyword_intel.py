"""keyword-intel 단방향 export 브릿지 소비자 테스트.

commerce-automation-kit(TS) → JSON export → wp-auto-blog 큐 (§8 단방향 계약).
거버넌스 의무를 코드로 강제:
  - schemaVersion·compliance 필수 (없거나 타입 위반이면 IngestError로 거부)
  - **보수모드 상시**: 질문 원문(source_questions)은 큐에 절대 저장 안 함
    (파이프라인이 소비하지도 않으므로 저장 = 순수 컴플라이언스 부채).
  - **항목 삭제 없음**: TTL은 legacy source_questions 필드만 제거(topic 등 가공물 보존 — §8).
  - dedup(재작성 안 함)은 completed/pending 모두 대상. 하드 게이트는 발행 시 파이프라인.
"""

import pytest

from scripts.ingest_keyword_intel import (
    IngestError,
    build_queue_item,
    ingest,
    purge_stale_questions,
    validate_export,
)

NOW = "2026-07-25T12:00:00"

VALID_EXPORT = {
    "schemaVersion": 1,
    "profile": "blog-kr",
    "generatedAt": "2026-07-25T00:00:00Z",
    "compliance": {"resaleRestricted": True, "cacheTtlHours": 24},
    "items": [
        {
            "topic": "국민내일배움카드 신청 자격과 방법 총정리",
            "keywords": ["국민내일배움카드", "신청자격"],
            "category": "생활정보",
            "monthly_search": 12000,
            "opportunity": 78,
            "source_questions": ["내일배움카드 어떻게 신청하나요?"],
        }
    ],
}


class TestValidateExport:
    def test_valid_passes(self):
        validate_export(VALID_EXPORT)

    def test_missing_compliance_rejected(self):
        bad = {k: v for k, v in VALID_EXPORT.items() if k != "compliance"}
        with pytest.raises(IngestError, match="compliance"):
            validate_export(bad)

    def test_missing_compliance_field_rejected(self):
        bad = {**VALID_EXPORT, "compliance": {"resaleRestricted": True}}
        with pytest.raises(IngestError, match="cacheTtlHours"):
            validate_export(bad)

    def test_unsupported_schema_version_rejected(self):
        with pytest.raises(IngestError, match="schemaVersion"):
            validate_export({**VALID_EXPORT, "schemaVersion": 99})

    def test_non_integer_ttl_rejected(self):
        bad = {**VALID_EXPORT, "compliance": {"resaleRestricted": True, "cacheTtlHours": "24.5"}}
        with pytest.raises(IngestError, match="cacheTtlHours"):
            validate_export(bad)

    def test_null_ttl_rejected(self):
        bad = {**VALID_EXPORT, "compliance": {"resaleRestricted": True, "cacheTtlHours": None}}
        with pytest.raises(IngestError, match="cacheTtlHours"):
            validate_export(bad)


class TestBuildQueueItem:
    def test_never_persists_source_questions(self):
        """보수모드 상시 — 질문 원문은 큐에 절대 실리지 않는다."""
        item = build_queue_item(VALID_EXPORT["items"][0], now=NOW)
        assert "source_questions" not in item
        assert item["topic"] == "국민내일배움카드 신청 자격과 방법 총정리"
        assert item["status"] == "pending"
        assert item["source"] == "cak_keyword_intel"
        assert item["ingested_at"] == NOW

    def test_derived_fields_carried(self):
        item = build_queue_item(VALID_EXPORT["items"][0], now=NOW)
        assert item["keywords"] == ["국민내일배움카드", "신청자격"]
        assert item["category"] == "생활정보"
        assert item["monthly_search"] == 12000
        assert item["opportunity"] == 78


class TestPurgeStaleQuestions:
    """TTL은 legacy source_questions 필드만 제거 — 항목(topic)은 절대 삭제 안 함."""

    def test_expired_questions_field_stripped_topic_kept(self):
        queue = [{
            "topic": "legacy cak", "source": "cak_keyword_intel",
            "ingested_at": "2026-07-24T00:00:00", "status": "pending",
            "source_questions": ["원문질문"],  # 36h 경과
        }]
        kept, purged = purge_stale_questions(queue, now=NOW, ttl_hours=24)
        assert purged == 1
        assert len(kept) == 1                      # 항목 유지
        assert kept[0]["topic"] == "legacy cak"    # topic 보존
        assert "source_questions" not in kept[0]   # 필드만 제거

    def test_fresh_questions_kept(self):
        queue = [{
            "topic": "x", "source": "cak_keyword_intel",
            "ingested_at": "2026-07-25T06:00:00", "status": "pending",
            "source_questions": ["q"],  # 6h
        }]
        kept, purged = purge_stale_questions(queue, now=NOW, ttl_hours=24)
        assert purged == 0
        assert kept[0]["source_questions"] == ["q"]

    def test_item_without_questions_kept_intact(self):
        queue = [{"topic": "x", "source": "cak_keyword_intel",
                  "ingested_at": "2026-07-01T00:00:00", "status": "pending"}]
        kept, purged = purge_stale_questions(queue, now=NOW, ttl_hours=24)
        assert purged == 0 and len(kept) == 1 and kept[0]["topic"] == "x"

    def test_native_items_never_touched(self):
        queue = [{"topic": "native", "status": "completed",
                  "source_questions": ["nope"]}]  # cak 아님
        kept, purged = purge_stale_questions(queue, now=NOW, ttl_hours=24)
        assert purged == 0 and kept[0]["source_questions"] == ["nope"]


class TestIngest:
    def test_appends_new_pending_item(self):
        new_q, summary = ingest(VALID_EXPORT, [], now=NOW)
        assert summary["added"] == 1
        assert new_q[-1]["topic"] == "국민내일배움카드 신청 자격과 방법 총정리"
        assert new_q[-1]["source"] == "cak_keyword_intel"
        assert "source_questions" not in new_q[-1]

    def test_dedup_skips_pending(self):
        queue = [{"topic": "국민내일배움카드 신청 자격과 방법 총정리", "status": "pending"}]
        new_q, summary = ingest(VALID_EXPORT, queue, now=NOW)
        assert summary["added"] == 0 and summary["skipped_dup"] == 1
        assert len(new_q) == 1

    def test_dedup_skips_completed(self):
        """이미 발행(completed)된 토픽은 재발행 안 함 — 재작성 금지 규칙."""
        queue = [{"topic": "국민내일배움카드 신청 자격과 방법 총정리", "status": "completed"}]
        new_q, summary = ingest(VALID_EXPORT, queue, now=NOW)
        assert summary["added"] == 0 and summary["skipped_dup"] == 1

    def test_expired_completed_not_requeued(self):
        """오래된 completed cak 항목이 삭제되지 않으므로 재큐잉되지 않는다."""
        queue = [{"topic": "국민내일배움카드 신청 자격과 방법 총정리",
                  "source": "cak_keyword_intel", "status": "completed",
                  "ingested_at": "2026-07-01T00:00:00"}]
        new_q, summary = ingest(VALID_EXPORT, queue, now=NOW)
        assert summary["added"] == 0
        assert any(q["topic"] == "국민내일배움카드 신청 자격과 방법 총정리"
                   and q["status"] == "completed" for q in new_q)

    def test_idempotent(self):
        q1, _ = ingest(VALID_EXPORT, [], now=NOW)
        q2, summary = ingest(VALID_EXPORT, q1, now="2026-07-25T13:00:00")
        assert summary["added"] == 0 and len(q2) == 1

    def test_invalid_export_raises(self):
        bad = {k: v for k, v in VALID_EXPORT.items() if k != "compliance"}
        with pytest.raises(IngestError):
            ingest(bad, [], now=NOW)

    def test_dict_queue_rejected(self):
        with pytest.raises(IngestError, match="list"):
            ingest(VALID_EXPORT, {"not": "a list"}, now=NOW)


class TestRobustness:
    def test_null_topic_skipped_not_crash(self):
        """topic=null 항목은 스킵하되 배치의 유효 항목은 살린다 (배치 손실 없음)."""
        exp = {**VALID_EXPORT,
               "items": [{"topic": None, "keywords": [], "category": "x"},
                         VALID_EXPORT["items"][0]]}
        new_q, summary = ingest(exp, [], now=NOW)
        assert summary["added"] == 1
        assert summary["skipped_dup"] == 1  # null도 스킵으로 집계

    def test_numeric_topic_skipped(self):
        exp = {**VALID_EXPORT, "items": [{"topic": 123, "category": "x"}]}
        new_q, summary = ingest(exp, [], now=NOW)
        assert summary["added"] == 0

    def test_blank_topic_skipped(self):
        exp = {**VALID_EXPORT, "items": [{"topic": "   ", "category": "x"}]}
        new_q, summary = ingest(exp, [], now=NOW)
        assert summary["added"] == 0
