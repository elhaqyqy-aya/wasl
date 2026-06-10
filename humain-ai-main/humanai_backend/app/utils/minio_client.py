from minio import Minio
from minio.error import S3Error
from app.config import settings
import io

def get_minio_client() -> Minio:
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )

def ensure_bucket(client: Minio, bucket: str):
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)

def upload_bytes(bucket: str, object_name: str, data: bytes, content_type: str = "application/pdf") -> str:
    client = get_minio_client()
    ensure_bucket(client, bucket)
    client.put_object(bucket, object_name, io.BytesIO(data), len(data), content_type=content_type)
    return f"{bucket}/{object_name}"

def download_bytes(bucket: str, object_name: str) -> bytes:
    client = get_minio_client()
    response = client.get_object(bucket, object_name)
    return response.read()

def get_presigned_url(bucket: str, object_name: str, expires_hours: int = 1) -> str:
    from datetime import timedelta
    client = get_minio_client()
    return client.presigned_get_object(bucket, object_name, expires=timedelta(hours=expires_hours))
