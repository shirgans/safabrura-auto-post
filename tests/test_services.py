"""Basic tests for services."""

import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from src.models.lecture import Lecture
from src.services.ffmpeg_converter import FFmpegConverter
from src.services.s3_upload import S3UploadService


class TestLectureModel:
    """Tests for the Lecture data model."""

    def test_from_drive_file_with_date(self):
        """Test parsing filename with date."""
        lecture = Lecture.from_drive_file(
            "abc123",
            "Introduction to Python - 2024-01-15.mp4"
        )

        assert lecture.drive_file_id == "abc123"
        assert lecture.title == "Introduction to Python"
        assert lecture.lecture_date == datetime(2024, 1, 15)
        assert lecture.formatted_date == "2024-01-15"

    def test_from_drive_file_without_date(self):
        """Test parsing filename without date."""
        lecture = Lecture.from_drive_file(
            "abc123",
            "Some Random Lecture.mp4"
        )

        assert lecture.title == "Some Random Lecture"
        assert lecture.lecture_date is None
        assert lecture.formatted_date == "Unknown Date"

    def test_add_error(self):
        """Test adding errors to a lecture."""
        lecture = Lecture.from_drive_file("abc", "test.mp4")

        assert not lecture.has_errors
        lecture.add_error("Something went wrong")
        assert lecture.has_errors
        assert len(lecture.errors) == 1


class TestFFmpegConverter:
    """Tests for the FFmpeg converter service."""

    def test_convert_to_mp3_file_not_found(self):
        """Test that conversion fails when file doesn't exist."""
        converter = FFmpegConverter()
        fake_path = Path("/nonexistent/video.mp4")

        with pytest.raises(FileNotFoundError):
            converter.convert_to_mp3(fake_path)

    @patch("subprocess.run")
    def test_check_ffmpeg_available(self, mock_run):
        """Test FFmpeg availability check."""
        mock_run.return_value = Mock(returncode=0)

        converter = FFmpegConverter()
        assert converter.check_ffmpeg_available() is True

    @patch("subprocess.run")
    def test_check_ffmpeg_not_available(self, mock_run):
        """Test FFmpeg not available."""
        mock_run.side_effect = FileNotFoundError()

        converter = FFmpegConverter()
        assert converter.check_ffmpeg_available() is False


class TestS3UploadService:
    """Tests for the S3 upload service."""

    def test_get_public_url(self):
        """Test public URL generation."""
        service = S3UploadService(
            bucket="test-bucket",
            region="us-east-1",
        )

        url = service.get_public_url("videos/test.mp4")
        expected = "https://test-bucket.s3.us-east-1.amazonaws.com/videos/test.mp4"
        assert url == expected

    def test_get_public_url_with_spaces(self):
        """Test URL encoding for filenames with spaces."""
        service = S3UploadService(
            bucket="test-bucket",
            region="us-east-1",
        )

        url = service.get_public_url("videos/my lecture.mp4")
        assert "my%20lecture.mp4" in url

    def test_generate_video_embed(self):
        """Test video embed code generation."""
        service = S3UploadService()
        url = "https://bucket.s3.region.amazonaws.com/video.mp4"

        embed = service.generate_video_embed(url)

        assert "<video" in embed
        assert f'src="{url}"' in embed
        assert 'type="video/mp4"' in embed

    def test_guess_content_type(self):
        """Test content type guessing."""
        service = S3UploadService()

        assert service._guess_content_type(Path("video.mp4")) == "video/mp4"
        assert service._guess_content_type(Path("audio.mp3")) == "audio/mpeg"
        assert service._guess_content_type(Path("unknown.xyz")) is None


class TestIntegration:
    """Integration tests (require actual credentials - skip by default)."""

    @pytest.mark.skip(reason="Requires actual AWS credentials")
    def test_s3_upload_real(self):
        """Test actual S3 upload."""
        pass

    @pytest.mark.skip(reason="Requires actual Google credentials")
    def test_drive_list_real(self):
        """Test actual Google Drive listing."""
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
