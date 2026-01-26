#!/usr/bin/env python3
"""Main entry point for wp-auto-blog pipeline.

Usage:
    # Run full pipeline for general blog (trendpulse.blog)
    python -m src.main --mode general

    # Run full pipeline for tech blog (bytepulse.io)
    python -m src.main --mode tech

    # Run with specific topic
    python -m src.main --mode tech --topic "Claude 3.5 Sonnet Review"

    # Dry run (no actual publishing)
    python -m src.main --mode general --dry-run

    # Auto-publish (not recommended initially)
    python -m src.main --mode general --auto-publish
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

from src.pipeline import BlogPipeline, PipelineConfig
from src.content_generator import ContentType, ContentConfig
from src.trend_detector import TrendConfig, TrendMode, TrendDetector


def setup_logging(verbose: bool = False) -> None:
    """Configure logging.

    Args:
        verbose: If True, enable debug logging
    """
    logger.remove()

    level = "DEBUG" if verbose else "INFO"
    fmt = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"

    logger.add(sys.stderr, format=fmt, level=level, colorize=True)

    # Also log to file
    log_dir = Path(__file__).parent.parent / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "pipeline.log",
        format=fmt,
        level="DEBUG",
        rotation="1 day",
        retention="7 days",
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="WordPress Auto Blog Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["tech", "general", "kculture"],
        required=True,
        help="Blog mode: 'tech' for bytepulse.io, 'general' for trendpulse.blog, 'kculture' for k-pulse.blog",
    )

    parser.add_argument(
        "--topic",
        type=str,
        help="Specific topic to write about (skips trend detection)",
    )

    parser.add_argument(
        "--keywords",
        type=str,
        nargs="+",
        help="Keywords for the topic (used with --topic)",
    )

    parser.add_argument(
        "--content-type",
        type=str,
        choices=["review", "comparison", "guide", "list", "news"],
        default="review",
        help="Type of content to generate (default: review)",
    )

    parser.add_argument(
        "--max-posts",
        type=int,
        default=3,
        help="Maximum posts per run (default: 3)",
    )

    parser.add_argument(
        "--category",
        type=str,
        help="WordPress category for posts",
    )

    parser.add_argument(
        "--auto-publish",
        action="store_true",
        help="Publish immediately instead of draft",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate run without actual publishing",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose/debug output",
    )

    parser.add_argument(
        "--use-api",
        action="store_true",
        help="Use Anthropic API instead of Claude CLI (for server deployment)",
    )

    parser.add_argument(
        "--no-llm-topics",
        action="store_true",
        help="Disable LLM-based topic analysis (use raw trending topics)",
    )

    parser.add_argument(
        "--from-queue",
        action="store_true",
        help="Process next pending topic from topic queue file",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Load environment variables
    load_dotenv()

    # Parse arguments
    args = parse_args()

    # Setup logging
    setup_logging(verbose=args.verbose)

    # Mode-specific site info
    site_info = {
        "tech": "bytepulse.io (Tech)",
        "general": "trendpulse.blog (General)",
        "kculture": "k-pulse.blog (K-Culture)",
    }

    logger.info("=" * 50)
    logger.info("WordPress Auto Blog Pipeline")
    logger.info(f"Mode: {args.mode.upper()} -> {site_info[args.mode]}")
    logger.info("=" * 50)

    # Map content type string to enum
    content_type_map = {
        "review": ContentType.REVIEW,
        "comparison": ContentType.COMPARISON,
        "guide": ContentType.GUIDE,
        "list": ContentType.LIST,
        "news": ContentType.NEWS,
    }

    # Map mode to TrendMode
    trend_mode_map = {
        "tech": TrendMode.TECH,
        "general": TrendMode.GENERAL,
        "kculture": TrendMode.KCULTURE,
    }

    # Create trend config based on mode
    trend_config = TrendConfig(mode=trend_mode_map[args.mode])

    # Map mode to language: general (trendpulse.blog) = Korean, tech/kculture = English
    language_map = {
        "general": "ko",   # trendpulse.blog - 한국어
        "tech": "en",      # bytepulse.io - English
        "kculture": "en",  # k-pulse.blog - English (US market)
    }

    # Create content config (CLI vs API mode + language)
    content_config = ContentConfig(
        use_cli=not args.use_api,  # Default: CLI mode, --use-api switches to API
        language=language_map.get(args.mode, "ko"),
    )

    # Create pipeline config
    config = PipelineConfig(
        max_posts_per_run=args.max_posts,
        content_type=content_type_map[args.content_type],
        auto_publish=args.auto_publish,
        dry_run=args.dry_run,
        category=args.category,
        mode=args.mode,  # 'tech' or 'general'
        use_llm_topics=not args.no_llm_topics,  # Default: True, --no-llm-topics disables
        trend_config=trend_config,
        content_config=content_config,
    )

    if args.dry_run:
        logger.info("[DRY RUN MODE] No posts will be published")

    # Initialize pipeline
    try:
        pipeline = BlogPipeline(config=config)
    except Exception as e:
        logger.error(f"Failed to initialize pipeline: {e}")
        return 1

    # Run pipeline
    try:
        if args.from_queue:
            # Queue mode - process next pending topic from queue file
            import json
            queue_file = Path(__file__).parent.parent / "data" / f"topic_queue_{args.mode}.json"

            if not queue_file.exists():
                logger.warning(f"Queue file not found: {queue_file}")
                return 0

            with open(queue_file, "r", encoding="utf-8") as f:
                queue = json.load(f)

            # Find next pending topic
            pending_topic = None
            pending_index = -1
            for i, item in enumerate(queue):
                if item.get("status") == "pending":
                    pending_topic = item
                    pending_index = i
                    break

            if not pending_topic:
                # For general mode, dynamically generate career topics
                if args.mode == "general":
                    logger.info("No pending topics in queue, generating career topics...")

                    # Create TrendDetector with general mode config
                    detector = TrendDetector(config=trend_config)
                    generated_topics = detector.generate_career_topics()

                    if not generated_topics:
                        logger.warning("Failed to generate career topics")
                        return 0

                    # Use the first generated topic
                    generated = generated_topics[0]
                    logger.info(f"Generated topic: {generated.suggested_title}")

                    # Create pending_topic dict from generated Topic
                    pending_topic = {
                        "topic": generated.suggested_title,
                        "keywords": generated.keywords,
                        "category": generated.category,
                        "status": "generated",  # Mark as dynamically generated
                    }
                    pending_index = -1  # No queue index for generated topics

                    # Optionally add to queue file for tracking
                    queue.append({
                        **pending_topic,
                        "generated_at": __import__("datetime").datetime.now().isoformat(),
                    })
                    with open(queue_file, "w", encoding="utf-8") as f:
                        json.dump(queue, f, ensure_ascii=False, indent=2)
                    logger.info("Added generated topic to queue for tracking")
                else:
                    logger.info("No pending topics in queue")
                    return 0

            logger.info(f"Processing from queue: {pending_topic['topic']}")

            # Process the topic
            result = pipeline.run_single(
                topic=pending_topic["topic"],
                keywords=pending_topic.get("keywords"),
            )
            results = [result]

            # Update queue status
            if result.success:
                if pending_index >= 0:
                    # Update existing queue item
                    queue[pending_index]["status"] = "completed"
                    queue[pending_index]["completed_at"] = __import__("datetime").datetime.now().isoformat()
                else:
                    # For generated topics, update the last item (which was just added)
                    queue[-1]["status"] = "completed"
                    queue[-1]["completed_at"] = __import__("datetime").datetime.now().isoformat()

                with open(queue_file, "w", encoding="utf-8") as f:
                    json.dump(queue, f, ensure_ascii=False, indent=2)
                logger.info(f"Queue updated: marked as completed")

        elif args.topic:
            # Single topic mode
            logger.info(f"Processing single topic: {args.topic}")
            result = pipeline.run_single(
                topic=args.topic,
                keywords=args.keywords,
            )
            results = [result]
        else:
            # Full pipeline mode
            logger.info("Running full pipeline (trend detection + processing)")
            results = pipeline.run()

    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        return 1

    # Print summary
    logger.info("")
    logger.info("=" * 50)
    logger.info("SUMMARY")
    logger.info("=" * 50)

    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    logger.info(f"Total processed: {len(results)}")
    logger.info(f"Successful: {len(successful)}")
    logger.info(f"Failed: {len(failed)}")

    if successful:
        logger.info("")
        logger.info("Created Posts:")
        for result in successful:
            if result.post:
                logger.info(f"  - {result.post.title}")
                logger.info(f"    URL: {result.post.url}")
                logger.info(f"    Status: {result.post.status.value}")

    if failed:
        logger.info("")
        logger.info("Failed Topics:")
        for result in failed:
            logger.error(f"  - {result.topic}: {result.error}")

    # Return success if all processed successfully
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
