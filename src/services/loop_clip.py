"""Six-second background loops for lecture cards.

The archive lists lectures as cards, and a card carrying a few seconds of its
own recording says more than a title does. Half an hour in is the useful
place to cut: past the greetings and the settling down, into the shiur itself.

FFmpeg seeks into the S3 object over HTTP range requests, so making one of
these costs a few seconds and a few hundred KB of transfer — the seven-hour
recording is never downloaded.
"""

import json
import logging
import subprocess
from pathlib import Path

from src.config.settings import settings

logger = logging.getLogger(__name__)


class LoopClipMaker:
    """Cuts a short silent clip, and the poster frame that goes with it."""

    def __init__(self, ffmpeg_path: str | None = None, ffprobe_path: str | None = None):
        """Initialize the clip maker.

        Args:
            ffmpeg_path: Path to the ffmpeg executable. Uses settings if not given.
            ffprobe_path: Path to ffprobe. Derived from ffmpeg_path if not given.
        """
        self.ffmpeg_path = ffmpeg_path or settings.FFMPEG_PATH
        self.ffprobe_path = ffprobe_path or settings.FFPROBE_PATH

    def probe_duration(self, video_url: str) -> float | None:
        """How long is the recording, in seconds?

        Args:
            video_url: URL or path of the video.

        Returns:
            Duration in seconds, or None when ffprobe can't tell us.
        """
        cmd = [
            self.ffprobe_path,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            video_url,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(json.loads(result.stdout)["format"]["duration"])
        except (subprocess.CalledProcessError, FileNotFoundError, KeyError, ValueError) as e:
            logger.warning(f"Could not probe duration for {video_url}: {e}")
            return None

    def resolve_start(self, video_url: str, start: int) -> int:
        """Where to actually cut.

        The default sits half an hour in, which is inside every full-length
        shiur. A recording that stops before then — a short session, or one
        that was cut off — gets its midpoint instead, so it still produces a
        clip rather than six seconds of nothing.

        Args:
            video_url: URL of the video.
            start: The requested offset in seconds.

        Returns:
            An offset that leaves room for a whole clip.
        """
        duration = self.probe_duration(video_url)

        if duration is None:
            return start

        if duration < start + settings.LOOP_DURATION:
            fallback = max(0, int(duration / 2) - settings.LOOP_DURATION)
            logger.info(
                f"Recording is only {int(duration)}s; cutting at {fallback}s "
                f"instead of {start}s"
            )
            return fallback

        return start

    def make(self, video_url: str, output_dir: Path, basename: str, start: int) -> dict:
        """Cut the loop and its poster frame.

        Args:
            video_url: URL of the source video.
            output_dir: Directory to write into.
            basename: Filename stem for the outputs.
            start: Offset in seconds to cut from.

        Returns:
            Dict with 'clip', 'poster' (Paths) and 'start' (the offset used).

        Raises:
            RuntimeError: If FFmpeg fails or writes nothing.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        start = self.resolve_start(video_url, start)

        clip = output_dir / f"{basename}.mp4"
        poster = output_dir / f"{basename}.jpg"

        # -ss before -i so ffmpeg seeks rather than decoding up to the mark.
        self._run([
            self.ffmpeg_path,
            "-nostdin", "-v", "error", "-y",
            "-ss", str(start),
            "-i", video_url,
            "-t", str(settings.LOOP_DURATION),
            "-an",  # a card background is silent
            "-vf", f"scale={settings.LOOP_WIDTH}:-2,fps={settings.LOOP_FPS}",
            "-c:v", "libx264",
            "-crf", str(settings.LOOP_CRF),
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(clip),
        ])

        # The same frame as a still, so the card has something to show before
        # the clip loads and while someone's system asks for less motion.
        self._run([
            self.ffmpeg_path,
            "-nostdin", "-v", "error", "-y",
            "-ss", str(start),
            "-i", video_url,
            "-frames:v", "1",
            "-vf", f"scale={settings.LOOP_WIDTH}:-2",
            "-q:v", "4",
            str(poster),
        ])

        for path in (clip, poster):
            if not path.exists() or path.stat().st_size == 0:
                raise RuntimeError(f"FFmpeg produced nothing at {path}")

        logger.info(
            f"Cut a {settings.LOOP_DURATION}s loop at {start}s "
            f"({clip.stat().st_size // 1024} KB)"
        )

        return {"clip": clip, "poster": poster, "start": start}

    def _run(self, cmd: list[str]) -> None:
        """Run FFmpeg, turning its failures into something readable."""
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"FFmpeg failed: {e.stderr}") from e
        except FileNotFoundError as e:
            raise RuntimeError(
                f"FFmpeg not found at '{self.ffmpeg_path}'. "
                "Please install FFmpeg or set FFMPEG_PATH in .env"
            ) from e
