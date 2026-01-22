#!/usr/bin/env python3
"""Test K-Food posting on bytepulse.io."""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from loguru import logger

# Load env
load_dotenv("/Users/honghyeonjong/home/IdeaProjects/wp-auto-blog/.env")

# Override to use bytepulse.io for this test
os.environ["WP_KCULTURE_URL"] = "https://bytepulse.io"
os.environ["WP_KCULTURE_USERNAME"] = os.getenv("WP_TECH_USERNAME")
os.environ["WP_KCULTURE_APP_PASSWORD"] = os.getenv("WP_TECH_APP_PASSWORD")

from src.pipeline import BlogPipeline, PipelineConfig
from src.trend_detector import Topic, TrendSource

def test_kfood_post():
    """Test K-Food posting on bytepulse.io."""
    logger.info("=== K-Food Test on bytepulse.io ===")

    # Create pipeline config in kculture mode
    config = PipelineConfig(
        mode="kculture",
        auto_publish=False,  # Draft mode
        dry_run=False,
        category="K-Food",  # Set category in config
        use_scheduled_category=False,  # Use our specified category
    )
    pipeline = BlogPipeline(config=config)

    # Create Topic object
    test_topic = Topic(
        topic="Korean Spicy Ramen Taste Test 2025: Best Buldak Flavors Ranked",
        source=TrendSource.GOOGLE_TRENDS,
        keywords=["buldak", "korean ramen", "spicy noodles", "samyang", "korean food"],
        score=85,
        suggested_title="Korean Spicy Ramen Taste Test 2025: Best Buldak Flavors Ranked",
        category="K-Food",
    )

    logger.info(f"Topic: {test_topic.topic}")
    logger.info(f"Category: {test_topic.category}")

    # Run pipeline with single topic
    try:
        result = pipeline._process_topic(test_topic)

        if result.success and result.post:
            logger.success(f"Post created successfully!")
            logger.info(f"Post ID: {result.post.id}")
            logger.info(f"URL: {result.post.url}")
            logger.info(f"Status: {result.post.status.value}")
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
    test_kfood_post()
