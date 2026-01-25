"""Test video duration from Google Drive."""
from src.services.google_drive import GoogleDriveService

drive = GoogleDriveService()

# Get a sample file with more metadata
files = drive.service.files().list(
    q=f"'{drive.folder_id}' in parents and trashed=false",
    fields='files(id, name, size, mimeType, videoMediaMetadata)',
    pageSize=5
).execute()

for f in files.get('files', []):
    print(f'Name: {f.get("name")}')
    print(f'Size: {f.get("size")} bytes')
    vmm = f.get('videoMediaMetadata', {})
    duration_ms = vmm.get('durationMillis')
    if duration_ms:
        duration_min = int(duration_ms) / 1000 / 60
        print(f'Duration: {duration_ms} ms ({duration_min:.1f} minutes)')
    else:
        print('Duration: Not available')
    print('---')
