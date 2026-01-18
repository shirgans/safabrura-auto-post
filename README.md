# SafaBrura Automation

Automates the upload workflow for Google Meet lecture recordings to SafaBrura (WordPress) and Captivate.fm podcast.

## Features

- Watch Google Drive folder for new lecture recordings
- Upload video to AWS S3
- Convert video to MP3 using FFmpeg
- Upload audio to Captivate.fm as podcast episode
- Create WordPress draft post with embedded video and podcast player

## Requirements

- Python 3.11+
- FFmpeg installed and available in PATH
- Google Cloud service account with Drive API access
- AWS S3 bucket
- WordPress site with application password
- Captivate.fm account

## Installation

1. Create and activate virtual environment:

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

4. Set up Google Drive service account:
   - Create a service account in Google Cloud Console
   - Enable Google Drive API
   - Download the JSON key file
   - Share your Drive folder with the service account email

## Usage

### Check prerequisites

```bash
python -m src.main --check
```

### List new lectures (dry run)

```bash
python -m src.main --dry-run
```

### Process all new lectures

```bash
python -m src.main
```

### Process a specific file

```bash
python -m src.main --file-id YOUR_FILE_ID --filename "Lecture Title - 2024-01-15.mp4"
```

### Verbose output

```bash
python -m src.main -v
```

## Workflow

1. **Check Google Drive** - Find new video files in the specified folder
2. **Upload to S3** - Upload video and get public URL
3. **Convert to MP3** - Extract audio using FFmpeg
4. **Upload to Captivate.fm** - Create podcast episode
5. **Create WordPress Draft** - Create post with video and audio embeds
6. **Cleanup** - Delete local temp files

## Configuration

All configuration is done via environment variables (see `.env.example`):

| Variable | Description |
|----------|-------------|
| `GOOGLE_DRIVE_FOLDER_ID` | Google Drive folder to watch |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Path to service account JSON |
| `AWS_ACCESS_KEY_ID` | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |
| `AWS_S3_BUCKET` | S3 bucket name |
| `AWS_S3_REGION` | AWS region |
| `WORDPRESS_URL` | WordPress site URL |
| `WORDPRESS_USERNAME` | WordPress username |
| `WORDPRESS_APP_PASSWORD` | WordPress application password |
| `CAPTIVATE_API_TOKEN` | Captivate.fm API token |
| `CAPTIVATE_SHOW_ID` | Captivate.fm show ID |
| `TEMP_DOWNLOAD_PATH` | Local temp directory |
| `FFMPEG_PATH` | Path to FFmpeg executable |

## Testing

```bash
pytest tests/ -v
```

## Project Structure

```
safabrura-automation/
├── src/
│   ├── main.py              # CLI entry point
│   ├── orchestrator.py      # LangGraph workflow
│   ├── services/
│   │   ├── google_drive.py  # Google Drive API
│   │   ├── s3_upload.py     # AWS S3 uploads
│   │   ├── ffmpeg_converter.py  # Video to MP3
│   │   ├── captivate.py     # Captivate.fm API
│   │   └── wordpress.py     # WordPress REST API
│   ├── models/
│   │   └── lecture.py       # Data models
│   └── config/
│       └── settings.py      # Environment config
├── tests/
│   └── test_services.py
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```
