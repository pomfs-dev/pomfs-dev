import os
import json
import uuid
import time
from google.cloud import storage


def get_gcs_client():
    """Initialize GCS client from environment credentials."""
    credentials_json = os.environ.get("GOOGLE_CLOUD_CREDENTIALS")
    if not credentials_json:
        raise ValueError("GOOGLE_CLOUD_CREDENTIALS environment variable not set")
    
    try:
        credentials_dict = json.loads(credentials_json)
        from google.oauth2 import service_account
        credentials = service_account.Credentials.from_service_account_info(credentials_dict)
        return storage.Client(credentials=credentials, project=credentials_dict.get("project_id"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in GOOGLE_CLOUD_CREDENTIALS: {e}")


def upload_image_to_gcs(local_file_path, user_id="pomfs_ai", folder="ai-post-img"):
    """
    Upload image to Google Cloud Storage.
    
    Args:
        local_file_path: Path to local image file
        user_id: User ID for folder structure
        folder: Target folder in bucket (default: ai-post-img)
    
    Returns:
        str: Public URL of uploaded image or None if failed
    """
    try:
        if not os.path.exists(local_file_path):
            print(f"[GCS] File not found: {local_file_path}")
            return None
        
        bucket_name = os.environ.get("GOOGLE_CLOUD_BUCKET_NAME", "communitystorage2")
        
        client = get_gcs_client()
        bucket = client.bucket(bucket_name)
        
        timestamp = int(time.time() * 1000)
        unique_id = str(uuid.uuid4())[:8]
        original_name = os.path.basename(local_file_path)
        sanitized_name = "".join(c for c in original_name if c.isalnum() or c in ".-_")
        
        file_extension = os.path.splitext(local_file_path)[1].lower()
        if file_extension in ['.jpg', '.jpeg']:
            content_type = 'image/jpeg'
        elif file_extension == '.png':
            content_type = 'image/png'
        elif file_extension == '.webp':
            content_type = 'image/webp'
        else:
            content_type = 'image/jpeg'
        
        blob_name = f"{folder}/{user_id}/{timestamp}-{unique_id}-{sanitized_name}"
        blob = bucket.blob(blob_name)
        
        blob.upload_from_filename(local_file_path, content_type=content_type)
        
        # Note: blob.make_public() removed - bucket has allUsers read access via IAM
        # Uniform Bucket-Level Access enabled, so object-level ACL not needed
        public_url = blob.public_url
        
        print(f"[GCS] Uploaded: {blob_name} -> {public_url}")
        return public_url
        
    except Exception as e:
        print(f"[GCS] Upload error: {e}")
        import traceback
        traceback.print_exc()
        return None


def upload_from_url(image_url, user_id="pomfs_ai", folder="ai-post-img"):
    """
    Download image from URL and upload to GCS.
    
    Args:
        image_url: URL of the image to download
        user_id: User ID for folder structure
        folder: Target folder in bucket
    
    Returns:
        str: Public URL of uploaded image or None if failed
    """
    try:
        import requests
        import tempfile
        
        response = requests.get(image_url, timeout=30)
        if response.status_code != 200:
            print(f"[GCS] Failed to download image: {response.status_code}")
            return None
        
        content_type = response.headers.get('content-type', 'image/jpeg')
        if 'png' in content_type:
            ext = '.png'
        elif 'webp' in content_type:
            ext = '.webp'
        else:
            ext = '.jpg'
        
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name
        
        try:
            result = upload_image_to_gcs(tmp_path, user_id, folder)
            return result
        finally:
            os.unlink(tmp_path)
            
    except Exception as e:
        print(f"[GCS] URL upload error: {e}")
        return None
