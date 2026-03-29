"""Main entry point for SafaBrura automation."""

import argparse
import logging
import sys
from pathlib import Path

from src.config.settings import settings
from src.orchestrator import LectureWorkflow
from src.models.lecture import Lecture
from src.services.ffmpeg_converter import FFmpegConverter


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the application."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def check_prerequisites() -> list[str]:
    """Check that all prerequisites are met.

    Returns:
        List of error messages (empty if all good).
    """
    errors = []

    # Check environment variables
    missing = settings.validate()
    if missing:
        errors.append(f"Missing environment variables: {', '.join(missing)}")

    # Check FFmpeg
    converter = FFmpegConverter()
    if not converter.check_ffmpeg_available():
        errors.append(
            f"FFmpeg not found at '{settings.FFMPEG_PATH}'. "
            "Please install FFmpeg or set FFMPEG_PATH in .env"
        )

    return errors


def run_workflow(dry_run: bool = False) -> int:
    """Run the lecture upload workflow.

    Args:
        dry_run: If True, only check for new files without processing.

    Returns:
        Exit code (0 for success, 1 for errors).
    """
    logger = logging.getLogger(__name__)

    # Check prerequisites
    errors = check_prerequisites()
    if errors:
        for error in errors:
            logger.error(error)
        return 1

    workflow = LectureWorkflow()

    if dry_run:
        # Just list new files
        lectures = workflow.drive_service.get_new_lectures()
        if lectures:
            logger.info(f"Found {len(lectures)} new lectures:")
            for lecture in lectures:
                logger.info(f"  - {lecture.title} ({lecture.filename})")
        else:
            logger.info("No new lectures found.")
        return 0

    # Process all new lectures
    results = workflow.process_new_lectures()

    # Report results - distinguish between critical errors and warnings
    success_count = sum(1 for r in results if not r.get("critical_errors"))
    warning_count = sum(1 for r in results if r.get("captivate_warnings") and not r.get("critical_errors"))
    error_count = sum(1 for r in results if r.get("critical_errors"))

    logger.info(f"\nProcessing complete:")
    logger.info(f"  Successful: {success_count}")
    if warning_count:
        logger.info(f"  With warnings (Captivate): {warning_count}")
    logger.info(f"  With critical errors: {error_count}")

    for result in results:
        lecture = result["lecture"]
        critical_errors = result.get("critical_errors", [])
        captivate_warnings = result.get("captivate_warnings", [])
        
        if critical_errors:
            logger.warning(f"\n{lecture.title}:")
            for error in critical_errors:
                logger.warning(f"  - {error}")
        elif captivate_warnings:
            logger.info(f"\n{lecture.title}:")
            logger.info(f"  WordPress post: {result['wordpress_post_url']}")
            for warning in captivate_warnings:
                logger.warning(f"  - Warning: {warning}")
        else:
            logger.info(f"\n{lecture.title}:")
            logger.info(f"  WordPress post: {result['wordpress_post_url']}")

    # Only fail for critical errors (WordPress/S3/conversion failures)
    # Captivate failures are warnings, not critical
    return 0 if error_count == 0 else 1


def process_single_file(file_id: str, filename: str) -> int:
    """Process a single file by ID.

    Args:
        file_id: Google Drive file ID.
        filename: Original filename.

    Returns:
        Exit code (0 for success, 1 for errors).
    """
    logger = logging.getLogger(__name__)

    # Check prerequisites
    errors = check_prerequisites()
    if errors:
        for error in errors:
            logger.error(error)
        return 1

    lecture = Lecture.from_drive_file(file_id, filename)
    workflow = LectureWorkflow()
    result = workflow.process_lecture(lecture)

    if result["errors"]:
        logger.error("Processing completed with errors:")
        for error in result["errors"]:
            logger.error(f"  - {error}")
        return 1

    logger.info("Processing completed successfully!")
    logger.info(f"WordPress post: {result['wordpress_post_url']}")
    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="SafaBrura Automation - Upload lecture recordings"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List new files without processing",
    )
    parser.add_argument(
        "--file-id",
        type=str,
        help="Process a specific Google Drive file ID",
    )
    parser.add_argument(
        "--filename",
        type=str,
        help="Filename for the specified file ID",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check prerequisites only",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    if args.check:
        errors = check_prerequisites()
        if errors:
            logger.error("Prerequisites check failed:")
            for error in errors:
                logger.error(f"  - {error}")
            return 1
        logger.info("All prerequisites met!")
        return 0

    if args.file_id:
        if not args.filename:
            logger.error("--filename is required when using --file-id")
            return 1
        return process_single_file(args.file_id, args.filename)

    return run_workflow(args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
