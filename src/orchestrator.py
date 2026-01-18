"""LangGraph orchestrator for the lecture upload workflow."""

import io
import logging
import re
from pathlib import Path
from typing import TypedDict

from langgraph.graph import StateGraph, END

from src.config.settings import settings
from src.models.lecture import Lecture
from src.services.google_drive import GoogleDriveService
from src.services.s3_upload import S3UploadService
from src.services.ffmpeg_converter import FFmpegConverter
from src.services.captivate import CaptivateService
from src.services.wordpress import WordPressService
from src.services.tracking import ProcessingTracker
from src.utils.hebrew_dates import format_lecture_title, get_category_for_date, get_hebrew_date_string


logger = logging.getLogger(__name__)


class WorkflowState(TypedDict):
    """State object passed between workflow nodes."""

    lecture: Lecture
    video_path: Path | None
    mp3_path: Path | None
    s3_url: str | None
    s3_key: str | None
    s3_embed_code: str | None
    captivate_episode_id: str | None
    captivate_mp3_url: str | None
    captivate_embed_code: str | None
    wordpress_post_id: int | None
    wordpress_post_url: str | None
    errors: list[str]
    current_step: str


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for S3 key (remove special characters)."""
    # Remove RTL/LTR markers and other unicode control characters
    filename = re.sub(r'[\u200e\u200f\u202a-\u202e]', '', filename)
    # Replace spaces and special chars with underscores
    filename = re.sub(r'[^\w\-.]', '_', filename)
    # Remove multiple underscores
    filename = re.sub(r'_+', '_', filename)
    return filename.strip('_')


class LectureWorkflow:
    """Orchestrates the lecture upload workflow using LangGraph.

    Optimized flow (no local video download):
    1. Stream video from Google Drive directly to S3
    2. FFmpeg reads from S3 URL to create MP3 (only MP3 saved locally)
    3. Upload MP3 to Captivate.fm
    4. Create WordPress draft post
    5. Cleanup (only MP3 to delete)
    """

    def __init__(self):
        """Initialize the workflow with all services."""
        self.drive_service = GoogleDriveService()
        self.s3_service = S3UploadService()
        self.ffmpeg_converter = FFmpegConverter()
        self.captivate_service = CaptivateService()
        self.wordpress_service = WordPressService()
        self.tracker = ProcessingTracker()
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(WorkflowState)

        # Add nodes - optimized flow
        workflow.add_node("stream_to_s3", self._stream_to_s3)
        workflow.add_node("convert_to_mp3", self._convert_to_mp3)
        workflow.add_node("upload_to_captivate", self._upload_to_captivate)
        workflow.add_node("create_wordpress_post", self._create_wordpress_post)
        workflow.add_node("cleanup", self._cleanup)

        # Define edges (linear flow)
        workflow.set_entry_point("stream_to_s3")
        workflow.add_edge("stream_to_s3", "convert_to_mp3")
        workflow.add_edge("convert_to_mp3", "upload_to_captivate")
        workflow.add_edge("upload_to_captivate", "create_wordpress_post")
        workflow.add_edge("create_wordpress_post", "cleanup")
        workflow.add_edge("cleanup", END)

        return workflow.compile()

    def _stream_to_s3(self, state: WorkflowState) -> WorkflowState:
        """Stream video directly from Google Drive to S3 (no local download)."""
        logger.info(f"Streaming video to S3: {state['lecture'].filename}")
        state["current_step"] = "stream_to_s3"

        try:
            # Create sanitized S3 key
            s3_key = f"videos/{sanitize_filename(state['lecture'].filename)}"
            if not s3_key.endswith('.mp4'):
                s3_key += '.mp4'

            # Stream from Google Drive to S3
            from googleapiclient.http import MediaIoBaseDownload

            request = self.drive_service.service.files().get_media(
                fileId=state["lecture"].drive_file_id
            )
            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)

            logger.info("Downloading from Google Drive...")
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logger.info(f"Download progress: {int(status.progress() * 100)}%")

            buffer.seek(0)

            logger.info("Uploading to S3...")
            s3_url = self.s3_service.upload_fileobj(
                buffer, s3_key, content_type="video/mp4"
            )

            state["s3_url"] = s3_url
            state["s3_key"] = s3_key
            state["s3_embed_code"] = self.s3_service.generate_video_embed(s3_url)
            state["lecture"].s3_url = s3_url
            state["lecture"].s3_embed_code = state["s3_embed_code"]

            logger.info(f"Streamed to S3: {s3_url}")
        except Exception as e:
            error = f"Failed to stream to S3: {e}"
            logger.error(error)
            state["errors"].append(error)
            state["lecture"].add_error(error)

        return state

    def _convert_to_mp3(self, state: WorkflowState) -> WorkflowState:
        """Convert video to MP3 by reading directly from S3 URL."""
        logger.info("Converting video to MP3 from S3 URL")
        state["current_step"] = "convert_to_mp3"

        if not state["s3_url"]:
            state["errors"].append("No S3 URL to convert from")
            return state

        try:
            # Create output path for MP3
            settings.ensure_temp_dir()
            mp3_filename = sanitize_filename(state["lecture"].filename)
            if mp3_filename.endswith('.mp4'):
                mp3_filename = mp3_filename[:-4]
            mp3_path = settings.TEMP_DOWNLOAD_PATH / f"{mp3_filename}.mp3"

            # FFmpeg reads directly from S3 URL
            logger.info(f"FFmpeg converting from URL: {state['s3_url']}")
            mp3_path = self.ffmpeg_converter.convert_url_to_mp3(
                video_url=state["s3_url"],
                output_path=mp3_path,
            )

            state["mp3_path"] = mp3_path
            state["lecture"].mp3_path = mp3_path
            logger.info(f"Converted to MP3: {mp3_path}")
        except Exception as e:
            error = f"Failed to convert to MP3: {e}"
            logger.error(error)
            state["errors"].append(error)
            state["lecture"].add_error(error)

        return state

    def _upload_to_captivate(self, state: WorkflowState) -> WorkflowState:
        """Upload MP3 to Captivate.fm."""
        logger.info("Uploading to Captivate.fm")
        state["current_step"] = "upload_to_captivate"

        if not state["mp3_path"]:
            state["errors"].append("No MP3 file to upload")
            return state

        try:
            result = self.captivate_service.upload_episode(
                mp3_path=state["mp3_path"],
                title=state["lecture"].title,
                description=f"הרצאה מתאריך {state['lecture'].formatted_date}",
                publish=True,
            )
            state["captivate_episode_id"] = result["episode_id"]
            state["captivate_mp3_url"] = result["mp3_url"]
            state["captivate_embed_code"] = result["embed_code"]

            state["lecture"].captivate_episode_id = result["episode_id"]
            state["lecture"].captivate_mp3_url = result["mp3_url"]
            state["lecture"].captivate_embed_code = result["embed_code"]

            logger.info(f"Uploaded to Captivate: {result['episode_id']}")
        except Exception as e:
            error = f"Failed to upload to Captivate: {e}"
            logger.error(error)
            state["errors"].append(error)
            state["lecture"].add_error(error)

        return state

    def _create_wordpress_post(self, state: WorkflowState) -> WorkflowState:
        """Create WordPress draft post with Hebrew formatted title and category."""
        logger.info("Creating WordPress draft post")
        state["current_step"] = "create_wordpress_post"

        try:
            lecture = state["lecture"]
            
            # Format the title with Hebrew day and date
            formatted_title = format_lecture_title(
                lecture.filename,
                lecture.lecture_date
            )
            
            # Find the Hebrew year category (e.g., תשפ"ו)
            category_ids = None
            if lecture.lecture_date:
                year_category = get_category_for_date(lecture.lecture_date)
                cat_id = self.wordpress_service.find_category_by_name(year_category)
                if cat_id:
                    category_ids = [cat_id]
                    logger.info(f"Using category: {year_category} (ID: {cat_id})")
                else:
                    logger.info(f"Category not found: {year_category}")
            
            # Build ACF custom fields
            acf_meta = {}
            
            # Lecture details fields
            if lecture.lecture_date:
                # Hebrew date (e.g., "כ"ח טבת")
                acf_meta["hebrew_date"] = get_hebrew_date_string(lecture.lecture_date)
                # Gregorian date (e.g., "14.1.26")
                acf_meta["gregorian_date"] = lecture.lecture_date.strftime("%d.%m.%y")
            
            # Captivate fields
            if state.get("captivate_episode_id"):
                episode_id = state["captivate_episode_id"]
                acf_meta["captivate_episode_player_url"] = f"https://player.captivate.fm/episode/{episode_id}"
            
            if state.get("captivate_mp3_url"):
                acf_meta["captivate_episode_mp3_url"] = state["captivate_mp3_url"]
                acf_meta["audio_file"] = state["captivate_mp3_url"]
            
            # Simple content - just the video since theme handles audio player
            content = ""
            if lecture.s3_url:
                poster_attr = f' poster="{settings.VIDEO_POSTER_URL}"' if settings.VIDEO_POSTER_URL else ''
                content = (
                    f"<h2>צפייה בהרצאה</h2>\n"
                    f'<video controls width="100%" preload="metadata"{poster_attr}>\n'
                    f'  <source src="{lecture.s3_url}" type="video/mp4">\n'
                    f"  הדפדפן שלך לא תומך בתגית וידאו.\n"
                    f"</video>"
                )
            
            # Create the post with ACF fields
            result = self.wordpress_service.create_draft_post(
                title=formatted_title,
                content=content,
                categories=category_ids,
                status="publish",
                acf=acf_meta,
            )
            
            state["wordpress_post_id"] = result["post_id"]
            state["wordpress_post_url"] = result["post_url"]

            state["lecture"].wordpress_post_id = result["post_id"]
            state["lecture"].wordpress_post_url = result["post_url"]

            logger.info(f"Created WordPress post: {result['post_id']} - {formatted_title}")
            logger.info(f"ACF fields: {list(acf_meta.keys())}")
        except Exception as e:
            error = f"Failed to create WordPress post: {e}"
            logger.error(error)
            state["errors"].append(error)
            state["lecture"].add_error(error)

        return state

    def _cleanup(self, state: WorkflowState) -> WorkflowState:
        """Clean up temporary files (only MP3 now, no local video)."""
        logger.info("Cleaning up temporary files")
        state["current_step"] = "cleanup"

        try:
            # Only MP3 needs cleanup (video was streamed directly to S3)
            if state["mp3_path"] and state["mp3_path"].exists():
                state["mp3_path"].unlink()
                logger.info(f"Deleted: {state['mp3_path']}")

            state["lecture"].processed = True
        except Exception as e:
            error = f"Cleanup warning: {e}"
            logger.warning(error)
            # Don't add to errors - cleanup failures are non-critical

        return state

    def process_lecture(self, lecture: Lecture) -> WorkflowState:
        """Process a single lecture through the workflow.

        Args:
            lecture: The Lecture object to process.

        Returns:
            The final workflow state.
        """
        # Check if already processed
        if self.tracker.is_processed(lecture.drive_file_id):
            logger.info(f"Skipping already processed: {lecture.filename}")
            return {
                "lecture": lecture,
                "video_path": None,
                "mp3_path": None,
                "s3_url": None,
                "s3_key": None,
                "s3_embed_code": None,
                "captivate_episode_id": None,
                "captivate_mp3_url": None,
                "captivate_embed_code": None,
                "wordpress_post_id": None,
                "wordpress_post_url": None,
                "errors": [],
                "current_step": "skipped",
            }

        initial_state: WorkflowState = {
            "lecture": lecture,
            "video_path": None,
            "mp3_path": None,
            "s3_url": None,
            "s3_key": None,
            "s3_embed_code": None,
            "captivate_episode_id": None,
            "captivate_mp3_url": None,
            "captivate_embed_code": None,
            "wordpress_post_id": None,
            "wordpress_post_url": None,
            "errors": [],
            "current_step": "init",
        }

        result = self.graph.invoke(initial_state)

        # Mark as processed if successful (no errors or only minor errors)
        if not result["errors"] and result["wordpress_post_url"]:
            self.tracker.mark_processed(
                file_id=lecture.drive_file_id,
                filename=lecture.filename,
                wordpress_url=result["wordpress_post_url"],
                captivate_episode_id=result["captivate_episode_id"],
                s3_url=result["s3_url"],
            )

        return result

    def process_new_lectures(self) -> list[WorkflowState]:
        """Find and process all new lectures.

        Returns:
            List of final workflow states for each lecture.
        """
        # Get all files and filter out already processed
        all_files = self.drive_service.list_video_files()
        unprocessed = self.tracker.get_unprocessed_files(all_files)
        
        logger.info(f"Found {len(all_files)} total files, {len(unprocessed)} unprocessed")

        results = []
        for file_info in unprocessed:
            lecture = Lecture.from_drive_file(file_info["id"], file_info["name"])
            logger.info(f"Processing: {lecture.title}")
            result = self.process_lecture(lecture)
            results.append(result)

            if result["errors"]:
                logger.warning(f"Completed with errors: {result['errors']}")
            else:
                logger.info("Completed successfully")

        return results
