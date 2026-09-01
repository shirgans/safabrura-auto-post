"""Cut a card loop for one lecture that already has a post.

The pipeline makes a loop for every new lecture, but the frame it lands on is
a matter of luck — sometimes it is the rabbanit mid-sentence, sometimes it is
someone crossing the room. The button on the post edit screen sends the post
here with a different offset to try again.

Usage:
    python src/generate_loop.py --post-id 13319 --video-url https://... [--start 1800]
"""

import argparse
import logging
import sys

from src.config.settings import settings
from src.services.loop_clip import LoopClipMaker
from src.services.s3_upload import S3UploadService
from src.services.wordpress import WordPressService

logger = logging.getLogger(__name__)


def slug_from_url(video_url: str) -> str:
    """The source filename, without its path or extension, for naming the clip."""
    from pathlib import PurePosixPath
    from urllib.parse import unquote, urlparse

    stem = PurePosixPath(unquote(urlparse(video_url).path)).stem
    return stem or "lecture"


def generate(post_id: int, video_url: str, start: int) -> dict:
    """Cut a loop, put it on S3, and write it onto the post.

    Args:
        post_id: The WordPress post to attach the loop to.
        video_url: The lecture's mp4, as embedded in that post.
        start: Offset in seconds to cut from.

    Returns:
        Dict with the loop URL, poster URL and the offset actually used.
    """
    maker = LoopClipMaker()
    s3 = S3UploadService()
    wordpress = WordPressService()

    basename = slug_from_url(video_url)

    settings.ensure_temp_dir()
    result = maker.make(
        video_url=video_url,
        output_dir=settings.TEMP_DOWNLOAD_PATH,
        basename=f"{basename}-loop",
        start=start,
    )

    # The offset is part of the key, so a second attempt at a different frame
    # gets its own URL and no cache anywhere can serve the old clip in its place.
    key = f"{settings.LOOP_S3_PREFIX}/{basename}-{result['start']}"
    loop_url = s3.upload_file(result["clip"], f"{key}.mp4", content_type="video/mp4")
    poster_url = s3.upload_file(result["poster"], f"{key}.jpg", content_type="image/jpeg")

    wordpress.update_post_meta(post_id, {
        "loop_video": loop_url,
        "loop_poster": poster_url,
        "loop_start": str(result["start"]),
    })

    for path in (result["clip"], result["poster"]):
        path.unlink(missing_ok=True)

    logger.info(f"Post {post_id} now has a loop cut at {result['start']}s: {loop_url}")

    return {"loop_video": loop_url, "loop_poster": poster_url, "start": result["start"]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Cut a card loop for one lecture post.")
    parser.add_argument("--post-id", type=int, required=True, help="WordPress post ID")
    parser.add_argument("--video-url", required=True, help="The lecture's mp4 URL")
    parser.add_argument(
        "--start",
        type=int,
        default=settings.LOOP_START,
        help="Seconds into the lecture to cut from (default: %(default)s)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        generate(args.post_id, args.video_url, args.start)
    except Exception as e:
        logger.error(f"Could not make the loop: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
