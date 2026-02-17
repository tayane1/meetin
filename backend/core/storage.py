import os
import uuid
from boto3 import client
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.files.base import ContentFile


class StorageService:
    """Service for handling S3-compatible storage operations"""
    
    def __init__(self):
        self.use_s3 = getattr(settings, 'USE_S3', False)
        
        if self.use_s3:
            self.s3_client = client(
                's3',
                aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY'),
                region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
            )
            self.bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME')
    
    def generate_upload_url(self, storage_key: str, content_type: str = 'audio/webm') -> str:
        """Generate presigned URL for direct upload"""
        if not self.use_s3:
            # For local storage, return a mock URL
            return f"http://localhost:8000/api/upload/{storage_key}"
        
        try:
            response = self.s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': storage_key,
                    'ContentType': content_type,
                },
                ExpiresIn=3600  # 1 hour
            )
            return response
        except ClientError as e:
            raise Exception(f"Failed to generate upload URL: {str(e)}")
    
    def generate_download_url(self, storage_key: str, expires_in: int = 3600) -> str:
        """Generate presigned URL for download"""
        if not self.use_s3:
            # For local storage, return a mock URL
            return f"http://localhost:8000/api/download/{storage_key}"
        
        try:
            response = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': storage_key,
                },
                ExpiresIn=expires_in
            )
            return response
        except ClientError as e:
            raise Exception(f"Failed to generate download URL: {str(e)}")
    
    def upload_file(self, storage_key: str, file_content: bytes, content_type: str = 'audio/webm') -> str:
        """Upload file directly to storage"""
        if not self.use_s3:
            # For local storage, save to media directory
            media_path = os.path.join(settings.MEDIA_ROOT, storage_key)
            os.makedirs(os.path.dirname(media_path), exist_ok=True)
            
            with open(media_path, 'wb') as f:
                f.write(file_content)
            
            return f"{settings.MEDIA_URL}{storage_key}"
        
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=storage_key,
                Body=file_content,
                ContentType=content_type
            )
            
            return f"https://{self.bucket_name}.s3.amazonaws.com/{storage_key}"
        except ClientError as e:
            raise Exception(f"Failed to upload file: {str(e)}")
    
    def delete_file(self, storage_key: str) -> bool:
        """Delete file from storage"""
        if not self.use_s3:
            # For local storage, delete from media directory
            media_path = os.path.join(settings.MEDIA_ROOT, storage_key)
            try:
                os.remove(media_path)
                return True
            except OSError:
                return False
        
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=storage_key
            )
            return True
        except ClientError:
            return False
    
    def file_exists(self, storage_key: str) -> bool:
        """Check if file exists in storage"""
        if not self.use_s3:
            # For local storage, check file system
            media_path = os.path.join(settings.MEDIA_ROOT, storage_key)
            return os.path.exists(media_path)
        
        try:
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=storage_key
            )
            return True
        except ClientError:
            return False
    
    def get_file_size(self, storage_key: str) -> int:
        """Get file size in bytes"""
        if not self.use_s3:
            # For local storage, check file system
            media_path = os.path.join(settings.MEDIA_ROOT, storage_key)
            if os.path.exists(media_path):
                return os.path.getsize(media_path)
            return 0
        
        try:
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=storage_key
            )
            return response.get('ContentLength', 0)
        except ClientError:
            return 0


# Global storage service instance
storage_service = StorageService()


# Convenience functions
def generate_upload_url(storage_key: str, content_type: str = 'audio/webm') -> str:
    """Generate presigned URL for upload"""
    return storage_service.generate_upload_url(storage_key, content_type)


def generate_download_url(storage_key: str, expires_in: int = 3600) -> str:
    """Generate presigned URL for download"""
    return storage_service.generate_download_url(storage_key, expires_in)


def upload_file(storage_key: str, file_content: bytes, content_type: str = 'audio/webm') -> str:
    """Upload file to storage"""
    return storage_service.upload_file(storage_key, file_content, content_type)


def delete_audio_file(storage_key: str) -> bool:
    """Delete audio file from storage"""
    return storage_service.delete_file(storage_key)


def get_audio_file(storage_key: str):
    """Get audio file for processing (returns file-like object)"""
    if not storage_service.use_s3:
        # For local storage, return file handle
        media_path = os.path.join(settings.MEDIA_ROOT, storage_key)
        if os.path.exists(media_path):
            return open(media_path, 'rb')
        return None
    
    # For S3, return the storage key and let the service handle it
    return {'bucket': storage_service.bucket_name, 'key': storage_key}