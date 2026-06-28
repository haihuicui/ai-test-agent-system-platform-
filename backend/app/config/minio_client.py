"""
MinIO 对象存储客户端

管理 MinIO 的连接和操作
"""

import io
from typing import Optional, BinaryIO
from datetime import timedelta

from minio import Minio
from minio.error import S3Error

from app.config.settings import settings

# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2U1c5bGRRPT06MjI1MmY5NmI=

class MinIOError(Exception):
    """MinIO 操作错误的包装类，用于避免 S3Error 的 frozen 属性问题"""

    def __init__(self, message: str, code: Optional[str] = None, original_error: Optional[S3Error] = None):
        super().__init__(message)
        self.code = code
        self.original_error = original_error


class MinIOClient:
    """MinIO 客户端管理器"""

    _client: Optional[Minio] = None
    _bucket_ensured: bool = False

    @classmethod
    def get_client(cls) -> Minio:
        """获取 MinIO 客户端实例"""
        if cls._client is None:
            cls._client = Minio(
                endpoint=settings.minio_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                secure=settings.minio_secure,
                region=settings.minio_region,
            )
        return cls._client

    @classmethod
    def ensure_bucket(cls) -> None:
        """确保存储桶存在"""
        if cls._bucket_ensured:
            return

        client = cls.get_client()
        bucket_name = settings.minio_bucket

        try:
            if not client.bucket_exists(bucket_name):
                client.make_bucket(bucket_name)
        except S3Error as e:
            # 桶已存在，忽略错误
            if e.code != "BucketAlreadyOwnedByYou":
                raise MinIOError(
                    f"Failed to ensure bucket exists: {e.message}",
                    code=e.code,
                    original_error=e
                )

        cls._bucket_ensured = True
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2U1c5bGRRPT06MjI1MmY5NmI=
    
    @classmethod
    def upload_file(
        cls,
        object_name: str,
        data: BinaryIO,
        length: int,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        上传文件到 MinIO

        Args:
            object_name: 对象名称（存储路径）
            data: 文件数据流
            length: 文件长度
            content_type: 内容类型

        Returns:
            str: 对象名称
        """
        try:
            cls.ensure_bucket()
            client = cls.get_client()

            client.put_object(
                bucket_name=settings.minio_bucket,
                object_name=object_name,
                data=data,
                length=length,
                content_type=content_type,
            )

            return object_name
        except S3Error as e:
            raise MinIOError(
                f"Failed to upload file '{object_name}': {e.message}",
                code=e.code,
                original_error=e
            )
# noqa  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2U1c5bGRRPT06MjI1MmY5NmI=
    
    @classmethod
    def upload_bytes(
        cls,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        上传字节数据到 MinIO
        
        Args:
            object_name: 对象名称
            data: 字节数据
            content_type: 内容类型
            
        Returns:
            str: 对象名称
        """
        return cls.upload_file(
            object_name=object_name,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
    
    @classmethod
    def download_file(cls, object_name: str) -> bytes:
        """
        从 MinIO 下载文件

        Args:
            object_name: 对象名称

        Returns:
            bytes: 文件内容
        """
        try:
            client = cls.get_client()

            response = client.get_object(
                bucket_name=settings.minio_bucket,
                object_name=object_name,
            )

            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()
        except S3Error as e:
            raise MinIOError(
                f"Failed to download file '{object_name}': {e.message}",
                code=e.code,
                original_error=e
            )
    
    @classmethod
    def get_presigned_url(
        cls,
        object_name: str,
        expires: timedelta = timedelta(hours=1),
    ) -> str:
        """
        获取预签名 URL（用于下载）

        Args:
            object_name: 对象名称
            expires: 过期时间

        Returns:
            str: 预签名 URL
        """
        try:
            client = cls.get_client()

            return client.presigned_get_object(
                bucket_name=settings.minio_bucket,
                object_name=object_name,
                expires=expires,
            )
        except S3Error as e:
            raise MinIOError(
                f"Failed to get presigned URL for '{object_name}': {e.message}",
                code=e.code,
                original_error=e
            )

    @classmethod
    def delete_file(cls, object_name: str) -> None:
        """
        从 MinIO 删除文件

        Args:
            object_name: 对象名称
        """
        try:
            client = cls.get_client()

            client.remove_object(
                bucket_name=settings.minio_bucket,
                object_name=object_name,
            )
        except S3Error as e:
            raise MinIOError(
                f"Failed to delete file '{object_name}': {e.message}",
                code=e.code,
                original_error=e
            )

    @classmethod
    def file_exists(cls, object_name: str) -> bool:
        """
        检查文件是否存在

        Args:
            object_name: 对象名称

        Returns:
            bool: 是否存在
        """
        try:
            client = cls.get_client()
# type: ignore  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2U1c5bGRRPT06MjI1MmY5NmI=

            client.stat_object(
                bucket_name=settings.minio_bucket,
                object_name=object_name,
            )
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            raise MinIOError(
                f"Failed to check if file '{object_name}' exists: {e.message}",
                code=e.code,
                original_error=e
            )

