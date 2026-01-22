#!/usr/bin/env python3
"""Test K-Fashion posting on bytepulse.io."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from loguru import logger

load_dotenv("/Users/honghyeonjong/home/IdeaProjects/wp-auto-blog/.env")

from src.pipeline import BlogPipeline, PipelineConfig
from src.trend_detector import Topic, TrendSource

def test_kfashion_post():
    logger.info("=== K-Fashion Test on bytepulse.io ===")

    config = PipelineConfig(
        mode="kculture",
        auto_publish=False,
        dry_run=False,
        category="K-Fashion",
        use_scheduled_category=False,
    )
    pipeline = BlogPipeline(config=config)

    test_topic = Topic(
        topic="Korean Minimalist Fashion Guide 2025: Seoul Street Style Essentials",
        source=TrendSource.GOOGLE_TRENDS,
        keywords=["korean fashion", "minimalist style", "seoul streetwear", "k-fashion", "korean outfit"],
        score=85,
        suggested_title="Korean Minimalist Fashion Guide 2025: Seoul Street Style Essentials",
        category="K-Fashion",
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
    test_kfashion_post()
