"""S3 service for uploading video files."""

import io
from pathlib import Path
from typing import BinaryIO
from urllib.parse import quote

import boto3
from botocore.exceptions import ClientError

from src.config.settings import settings


class S3UploadService:
    """Service for uploading files to AWS S3."""

    def __init__(
        self,
        bucket: str | None = None,
        region: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ):
        """Initialize the S3 service.

        Args:
            bucket: S3 bucket name.
            region: AWS region.
            access_key_id: AWS access key ID.
            secret_access_key: AWS secret access key.
        """
        self.bucket = bucket or settings.AWS_S3_BUCKET
        self.region = region or settings.AWS_S3_REGION
        self._client = None
        self._access_key_id = access_key_id or settings.AWS_ACCESS_KEY_ID
        self._secret_access_key = secret_access_key or settings.AWS_SECRET_ACCESS_KEY

    @property
    def client(self):
        """Get or create the S3 client."""
        if self._client is None:
            self._client = boto3.client(
                "s3",
                region_name=self.region,
                aws_access_key_id=self._access_key_id,
                aws_secret_access_key=self._secret_access_key,
            )
        return self._client

    def upload_file(
        self,
        file_path: Path,
        s3_key: str | None = None,
        content_type: str | None = None,
    ) -> str:
        """Upload a file to S3.

        Args:
            file_path: Local path to the file to upload.
            s3_key: S3 object key. Uses filename if not provided.
            content_type: MIME type of the file.

        Returns:
            The public URL of the uploaded file.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            RuntimeError: If the upload fails.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if s3_key is None:
            s3_key = file_path.name

        # Determine content type
        if content_type is None:
            content_type = self._guess_content_type(file_path)

        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type

        try:
            self.client.upload_file(
                str(file_path),
                self.bucket,
                s3_key,
                ExtraArgs=extra_args,
            )
        except ClientError as e:
            raise RuntimeError(f"Failed to upload to S3: {e}") from e

        return self.get_public_url(s3_key)

    def upload_fileobj(
        self,
        fileobj: BinaryIO,
        s3_key: str,
        content_type: str | None = None,
    ) -> str:
        """Upload a file-like object to S3.

        Args:
            fileobj: File-like object to upload.
            s3_key: S3 object key.
            content_type: MIME type of the file.

        Returns:
            The public URL of the uploaded file.

        Raises:
            RuntimeError: If the upload fails.
        """
        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type

        try:
            self.client.upload_fileobj(
                fileobj,
                self.bucket,
                s3_key,
                ExtraArgs=extra_args if extra_args else None,
            )
        except ClientError as e:
            raise RuntimeError(f"Failed to upload to S3: {e}") from e

        return self.get_public_url(s3_key)

    def get_public_url(self, s3_key: str) -> str:
        """Get the public URL for an S3 object.

        Args:
            s3_key: The S3 object key.

        Returns:
            The public URL.
        """
        encoded_key = quote(s3_key, safe="/")
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{encoded_key}"

    def generate_video_embed(self, s3_url: str) -> str:
        """Generate HTML embed code for a video.

        Args:
            s3_url: The S3 URL of the video.

        Returns:
            HTML video embed code.
        """
        return (
            f'<video controls width="100%">\n'
            f'  <source src="{s3_url}" type="video/mp4">\n'
            f"  Your browser does not support the video tag.\n"
            f"</video>"
        )

    def _guess_content_type(self, file_path: Path) -> str | None:
        """Guess the content type based on file extension."""
        extension_map = {
            ".mp4": "video/mp4",
            ".webm": "video/webm",
            ".mkv": "video/x-matroska",
            ".mov": "video/quicktime",
            ".mp3": "audio/mpeg",
        }
        return extension_map.get(file_path.suffix.lower())

    def check_bucket_access(self) -> bool:
        """Check if the bucket is accessible.

        Returns:
            True if the bucket is accessible, False otherwise.
        """
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return True
        except ClientError:
            return False
