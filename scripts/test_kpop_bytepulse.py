#!/usr/bin/env python3
"""Test K-Pop posting on bytepulse.io."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from loguru import logger

load_dotenv("/Users/honghyeonjong/home/IdeaProjects/wp-auto-blog/.env")

from src.pipeline import BlogPipeline, PipelineConfig
from src.trend_detector import Topic, TrendSource

def test_kpop_post():
    logger.info("=== K-Pop Test on bytepulse.io ===")

    config = PipelineConfig(
        mode="kculture",
        auto_publish=False,
        dry_run=False,
        category="K-Pop",
        use_scheduled_category=False,
    )
    pipeline = BlogPipeline(config=config)

    test_topic = Topic(
        topic="BLACKPINK World Tour 2025: Complete Concert Guide & Setlist",
        source=TrendSource.GOOGLE_TRENDS,
        keywords=["blackpink", "kpop concert", "world tour", "blink", "korean music"],
        score=90,
        suggested_title="BLACKPINK World Tour 2025: Complete Concert Guide & Setlist",
        category="K-Pop",
    )

    logger.info(f"Topic: {test_topic.topic}")
    logger.info(f"Category: {test_topic.category}")

    try:
        result = pipeline._process_topic(test_topic)

        if result.success and result.post:
            logger.success(f"Post created successfully!")
            logger.info(f"Post ID: {result.post.id}")
            logger.info(f"URL: {result.post.url}")
            return True
        else:
            logger.error(f"Pipeline failed: {result.error}")
            return False

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_kpop_post()
