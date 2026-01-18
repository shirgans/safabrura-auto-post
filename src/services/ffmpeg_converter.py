"""FFmpeg service for converting video to MP3."""

import subprocess
from pathlib import Path

from src.config.settings import settings


class FFmpegConverter:
    """Convert video files to MP3 using FFmpeg."""

    def __init__(self, ffmpeg_path: str | None = None):
        """Initialize the converter.

        Args:
            ffmpeg_path: Path to FFmpeg executable. Uses settings if not provided.
        """
        self.ffmpeg_path = ffmpeg_path or settings.FFMPEG_PATH

    def convert_to_mp3(
        self,
        video_path: Path,
        output_path: Path | None = None,
        bitrate: str = "192k",
    ) -> Path:
        """Convert a local video file to MP3.

        Args:
            video_path: Path to the input video file.
            output_path: Path for the output MP3. If not provided, uses same name as video.
            bitrate: Audio bitrate for the output MP3.

        Returns:
            Path to the created MP3 file.

        Raises:
            FileNotFoundError: If the input video doesn't exist.
            RuntimeError: If FFmpeg conversion fails.
        """
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        if output_path is None:
            output_path = video_path.with_suffix(".mp3")

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.ffmpeg_path,
            "-i",
            str(video_path),
            "-vn",  # No video
            "-acodec",
            "libmp3lame",
            "-ab",
            bitrate,
            "-y",  # Overwrite output
            str(output_path),
        ]

        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"FFmpeg conversion failed: {e.stderr}") from e
        except FileNotFoundError as e:
            raise RuntimeError(
                f"FFmpeg not found at '{self.ffmpeg_path}'. "
                "Please install FFmpeg or set FFMPEG_PATH in .env"
            ) from e

        if not output_path.exists():
            raise RuntimeError(f"FFmpeg did not create output file: {output_path}")

        return output_path

    def convert_url_to_mp3(
        self,
        video_url: str,
        output_path: Path,
        bitrate: str = "192k",
    ) -> Path:
        """Convert a video from URL directly to MP3.

        FFmpeg can read directly from HTTP/HTTPS URLs, avoiding local video download.

        Args:
            video_url: URL to the video file (e.g., S3 public URL).
            output_path: Path for the output MP3.
            bitrate: Audio bitrate for the output MP3.

        Returns:
            Path to the created MP3 file.

        Raises:
            RuntimeError: If FFmpeg conversion fails.
        """
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.ffmpeg_path,
            "-i",
            video_url,  # Read directly from URL
            "-vn",  # No video
            "-acodec",
            "libmp3lame",
            "-ab",
            bitrate,
            "-y",  # Overwrite output
            str(output_path),
        ]

        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"FFmpeg conversion failed: {e.stderr}") from e
        except FileNotFoundError as e:
            raise RuntimeError(
                f"FFmpeg not found at '{self.ffmpeg_path}'. "
                "Please install FFmpeg or set FFMPEG_PATH in .env"
            ) from e

        if not output_path.exists():
            raise RuntimeError(f"FFmpeg did not create output file: {output_path}")

        return output_path

    def check_ffmpeg_available(self) -> bool:
        """Check if FFmpeg is available and working.

        Returns:
            True if FFmpeg is available, False otherwise.
        """
        try:
            subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                check=True,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
