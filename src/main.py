#!/usr/bin/env python3
"""Main entry point for wp-auto-blog pipeline.

Usage:
    # Run full pipeline (detect trends, generate, publish as draft)
    python -m src.main

    # Run with specific topic
    python -m src.main --topic "Claude 3.5 Sonnet Review"

    # Dry run (no actual publishing)
    python -m src.main --dry-run

    # Auto-publish (not recommended initially)
    python -m src.main --auto-publish
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

from src.pipeline import BlogPipeline, PipelineConfig
from src.content_generator import ContentType


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

    logger.info("=" * 50)
    logger.info("WordPress Auto Blog Pipeline")
    logger.info("=" * 50)

    # Map content type string to enum
    content_type_map = {
        "review": ContentType.REVIEW,
        "comparison": ContentType.COMPARISON,
        "guide": ContentType.GUIDE,
        "list": ContentType.LIST,
        "news": ContentType.NEWS,
    }

    # Create pipeline config
    config = PipelineConfig(
        max_posts_per_run=args.max_posts,
        content_type=content_type_map[args.content_type],
        auto_publish=args.auto_publish,
        dry_run=args.dry_run,
        category=args.category,
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
        if args.topic:
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
