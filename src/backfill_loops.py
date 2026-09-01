"""Give lectures that already have posts their card loop.

New lectures get one from the pipeline, but the archive is years deep. This
walks back through published posts, finds the mp4 each one embeds, and cuts
the same six seconds for it.

Posts that already have a loop are left alone, so this can be run again to
pick up where a previous run stopped without redoing its work.

Usage:
    python src/backfill_loops.py --count 50
    python src/backfill_loops.py --count 50 --force   # recut existing ones too
"""

import argparse
import logging
import re
import sys
from html import unescape

from src.config.settings import settings
from src.generate_loop import generate
from src.services.wordpress import WordPressService

logger = logging.getLogger(__name__)

# The agent writes each lecture's recording into the post as a plain
# <video><source src="…s3…mp4"> block, so that is where the source lives.
SOURCE_RE = re.compile(r'<source[^>]+src=["\']([^"\']+\.mp4)["\']', re.IGNORECASE)


def video_url_for(post: dict) -> str | None:
    """The lecture's mp4, as embedded in its post content."""
    content = (post.get("content") or {}).get("rendered", "")
    match = SOURCE_RE.search(content)
    return unescape(match.group(1)) if match else None


def backfill(count: int, start: int, force: bool = False) -> dict:
    """Cut loops for the most recent posts that don't have one.

    Args:
        count: How many recent posts to consider.
        start: Offset in seconds to cut from.
        force: Recut posts that already have a loop.

    Returns:
        Counts of what happened, by outcome.
    """
    wordpress = WordPressService()
    tally = {"done": 0, "skipped": 0, "no_video": 0, "failed": 0}

    posts: list[dict] = []
    page = 1
    while len(posts) < count:
        batch = wordpress.list_posts(per_page=min(100, count - len(posts)), page=page)
        if not batch:
            break
        posts.extend(batch)
        page += 1

    logger.info(f"Looking at {len(posts)} posts")

    for index, post in enumerate(posts, 1):
        post_id = post["id"]
        title = (post.get("title") or {}).get("rendered", "")
        label = f"[{index}/{len(posts)}] {post_id} {title}"

        if not force and (post.get("meta") or {}).get("loop_video"):
            logger.info(f"{label} — already has a loop")
            tally["skipped"] += 1
            continue

        video_url = video_url_for(post)
        if not video_url:
            logger.info(f"{label} — no video in this post")
            tally["no_video"] += 1
            continue

        try:
            result = generate(post_id, video_url, start)
            logger.info(f"{label} — cut at {result['start']}s")
            tally["done"] += 1
        except Exception as e:
            # One bad recording shouldn't end the run; the rest still deserve
            # their loops, and this one can be retried on its own afterwards.
            logger.error(f"{label} — failed: {e}")
            tally["failed"] += 1

    return tally


def main() -> int:
    parser = argparse.ArgumentParser(description="Cut card loops for existing lecture posts.")
    parser.add_argument("--count", type=int, default=50, help="How many recent posts to consider")
    parser.add_argument(
        "--start",
        type=int,
        default=settings.LOOP_START,
        help="Seconds into each lecture to cut from (default: %(default)s)",
    )
    parser.add_argument("--force", action="store_true", help="Recut posts that already have a loop")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    tally = backfill(args.count, args.start, args.force)

    logger.info(
        "Finished: %(done)s cut, %(skipped)s already had one, "
        "%(no_video)s without video, %(failed)s failed" % tally
    )

    return 1 if tally["failed"] and not tally["done"] else 0


if __name__ == "__main__":
    sys.exit(main())
