import boto3
import uuid
import os
from datetime import datetime, timedelta
from typing import Optional, Tuple
from pathlib import Path
from dotenv import load_dotenv
import mimetypes

load_dotenv()

class S3ImageService:
    def __init__(self):
        # 環境に応じてエンドポイントを切り替え
        self.is_local = os.getenv('ENVIRONMENT', 'development') == 'development'
        
        if self.is_local:
            # LocalStack設定
            self.s3_client = boto3.client(
                's3',
                endpoint_url='http://localhost:4566',
                aws_access_key_id='test',
                aws_secret_access_key='test',
                region_name='us-east-1'
            )
            self.bucket_name = 'news-api-thumbnails'
            self.cloudfront_domain = None  # LocalStackではCloudFrontは簡易版
            self.base_url = 'http://localhost:4566'
        else:
            # 本番AWS設定
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                region_name=os.getenv('AWS_REGION', 'ap-northeast-1')
            )
            self.bucket_name = os.getenv('S3_BUCKET_NAME')
            self.cloudfront_domain = os.getenv('CLOUDFRONT_DOMAIN')
            self.base_url = f"https://{self.bucket_name}.s3.{os.getenv('AWS_REGION', 'ap-northeast-1')}.amazonaws.com"
        
        # バケットの存在確認・作成
        self._ensure_bucket_exists()
        
        # 許可する画像形式
        self.allowed_types = {
            'image/jpeg': '.jpg',
            'image/png': '.png', 
            'image/webp': '.webp',
            'image/gif': '.gif'
        }
        
        # キャッシュ設定
        self.cache_settings = {
            'short': 'max-age=3600, public',      # 1時間
            'medium': 'max-age=86400, public',    # 24時間
            'long': 'max-age=31536000, public'    # 1年
        }
    
    def _ensure_bucket_exists(self):
        """バケットの存在確認・作成"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            print(f"S3バケット確認: {self.bucket_name} (存在)")
        except Exception:
            try:
                if self.is_local:
                    # LocalStackの場合
                    self.s3_client.create_bucket(Bucket=self.bucket_name)
                    print(f"S3バケット作成: {self.bucket_name} (LocalStack)")
                else:
                    # 本番環境の場合
                    region = os.getenv('AWS_REGION', 'ap-northeast-1')
                    if region == 'us-east-1':
                        # us-east-1の場合はLocationConstraintを指定しない
                        self.s3_client.create_bucket(Bucket=self.bucket_name)
                    else:
                        self.s3_client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': region}
                        )
                    print(f"S3バケット作成: {self.bucket_name} (AWS)")
            except Exception as e:
                print(f"S3バケット作成失敗: {str(e)}")
                # バケット作成に失敗してもサービスは継続
    
    def upload_image(
        self, 
        file_content: bytes, 
        content_type: str,
        original_filename: str,
        cache_duration: str = 'long'
    ) -> Tuple[str, Optional[str], str]:
        """
        S3に画像をアップロードし、キャッシュ設定を適用
        
        Returns:
            Tuple[s3_url, cloudfront_url, filename]
        """
        if content_type not in self.allowed_types:
            raise ValueError(f"サポートされていないファイル形式: {content_type}")
        
        # ユニークなファイル名を生成
        file_extension = self.allowed_types[content_type]
        unique_filename = f"thumbnails/{uuid.uuid4()}{file_extension}"
        
        # キャッシュ制御ヘッダー
        cache_control = self.cache_settings.get(cache_duration, self.cache_settings['long'])
        expires = datetime.utcnow() + timedelta(days=365 if cache_duration == 'long' else 1)
        
        try:
            # S3にアップロード
            put_object_args = {
                'Bucket': self.bucket_name,
                'Key': unique_filename,
                'Body': file_content,
                'ContentType': content_type,
                'CacheControl': cache_control,
                'Metadata': {
                    'original-filename': original_filename,
                    'uploaded-at': datetime.utcnow().isoformat(),
                    'cache-strategy': cache_duration
                }
            }
            
            # LocalStackではExpiresヘッダーがサポートされていない場合があるため条件分岐
            if not self.is_local:
                put_object_args['Expires'] = expires
            
            self.s3_client.put_object(**put_object_args)
            
            # URLを生成
            if self.is_local:
                s3_url = f"{self.base_url}/{self.bucket_name}/{unique_filename}"
            else:
                s3_url = f"{self.base_url}/{unique_filename}"
            
            # CloudFront URLを生成（設定されている場合）
            cloudfront_url = None
            if self.cloudfront_domain and not self.is_local:
                cloudfront_url = f"https://{self.cloudfront_domain}/{unique_filename}"
            
            return s3_url, cloudfront_url, unique_filename
            
        except Exception as e:
            raise Exception(f"S3アップロードに失敗しました: {str(e)}")
    
    def delete_image(self, filename: str) -> bool:
        """S3から画像を削除"""
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=filename
            )
            return True
        except Exception as e:
            print(f"S3削除エラー: {str(e)}")
            return False
    
    def generate_presigned_url(self, filename: str, expiration: int = 3600) -> str:
        """署名付きURLを生成（プライベートファイル用）"""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': filename},
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            raise Exception(f"署名付きURL生成に失敗しました: {str(e)}")
    
    def get_image_info(self, filename: str) -> Optional[dict]:
        """S3からファイル情報を取得"""
        try:
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=filename
            )
            return {
                'size': response['ContentLength'],
                'content_type': response['ContentType'],
                'last_modified': response['LastModified'],
                'cache_control': response.get('CacheControl'),
                'metadata': response.get('Metadata', {}),
                'is_local': self.is_local
            }
        except Exception as e:
            print(f"ファイル情報取得エラー: {str(e)}")
            return None
    
    def list_images(self, prefix: str = "thumbnails/", max_keys: int = 100) -> list:
        """S3バケット内の画像一覧を取得"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            images = []
            for obj in response.get('Contents', []):
                images.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'],
                    'url': f"{self.base_url}/{self.bucket_name}/{obj['Key']}" if self.is_local else f"{self.base_url}/{obj['Key']}"
                })
            
            return images
        except Exception as e:
            print(f"画像一覧取得エラー: {str(e)}")
            return []
    
    def health_check(self) -> dict:
        """S3サービスのヘルスチェック"""
        try:
            # バケットの存在確認
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return {
                'status': 'healthy',
                'bucket': self.bucket_name,
                'endpoint': self.base_url,
                'is_local': self.is_local
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'is_local': self.is_local
            }

# シングルトンインスタンス
s3_service = S3ImageService() 