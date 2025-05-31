import os
import json
import uuid
import boto3
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr, BaseModel, validator
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from dotenv import load_dotenv
import asyncio
import redis

load_dotenv()

class EmailConfig:
    """メール設定クラス"""
    def __init__(self):
        self.is_local = os.getenv('ENVIRONMENT', 'development') == 'development'
        
        if self.is_local:
            # 開発環境: MailHog設定
            self.conf = ConnectionConfig(
                MAIL_USERNAME="",
                MAIL_PASSWORD="",
                MAIL_FROM="noreply@example.com",
                MAIL_PORT=1025,
                MAIL_SERVER="localhost",
                MAIL_STARTTLS=False,
                MAIL_SSL_TLS=False,
                USE_CREDENTIALS=False,
                VALIDATE_CERTS=False,
                TEMPLATE_FOLDER=None
            )
        else:
            # 本番環境: AWS SES または SMTP設定
            self.conf = ConnectionConfig(
                MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
                MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
                MAIL_FROM=os.getenv("MAIL_FROM", "noreply@example.com"),
                MAIL_PORT=int(os.getenv("MAIL_PORT", "587")),
                MAIL_SERVER=os.getenv("MAIL_SERVER", "smtp.gmail.com"),
                MAIL_STARTTLS=True,
                MAIL_SSL_TLS=False,
                USE_CREDENTIALS=True,
                VALIDATE_CERTS=True,
                TEMPLATE_FOLDER=None
            )

class ContactForm(BaseModel):
    """お問い合わせフォームのスキーマ"""
    name: Optional[str] = None
    email: EmailStr
    subject: str
    message: str
    phone: Optional[str] = None
    company: Optional[str] = None
    
    @validator('subject', 'message')
    def validate_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('必須項目は空にできません')
        return v.strip()
    
    @validator('name', 'phone', 'company', pre=True)
    def validate_optional_fields(cls, v):
        if v is not None and isinstance(v, str):
            v = v.strip()
            return v if v else None
        return v

class RateLimiter:
    """レート制限クラス"""
    def __init__(self):
        try:
            self.redis = redis.Redis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=int(os.getenv('REDIS_PORT', 6379)),
                db=0,
                decode_responses=True
            )
            self.available = True
        except Exception as e:
            print(f"Redis: 接続失敗 ({type(e).__name__})")
            self.available = False
    
    async def check_rate_limit(self, key: str, limit: int, period: int) -> bool:
        """レート制限をチェック"""
        if not self.available:
            return True  # Redisが利用できない場合は制限しない
        
        try:
            current = datetime.utcnow()
            key = f"rate_limit:{key}"
            
            # 古いエントリを削除
            self.redis.zremrangebyscore(key, 0, current.timestamp() - period)
            
            # 現在のカウントを取得
            count = self.redis.zcard(key)
            
            if count < limit:
                # 新しいエントリを追加
                self.redis.zadd(key, {str(current.timestamp()): current.timestamp()})
                self.redis.expire(key, period)
                return True
            
            return False
        except Exception as e:
            print(f"レート制限: チェック失敗 ({type(e).__name__})")
            return True  # エラーの場合は制限しない

class SNSService:
    """Amazon SNS通知サービス"""
    def __init__(self):
        try:
            self.is_local = os.getenv('ENVIRONMENT', 'development') == 'development'
            
            if self.is_local:
                # 開発環境ではSNSを無効化
                self.available = False
                print("開発環境のため、SNS通知は無効化されています")
            else:
                # 本番環境: AWS SNS設定
                self.sns = boto3.client(
                    'sns',
                    region_name=os.getenv('AWS_REGION', 'ap-northeast-1'),
                    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
                )
                self.topic_arn = os.getenv('SNS_TOPIC_ARN')
                self.available = bool(self.topic_arn)
                
                if not self.available:
                    print("SNS_TOPIC_ARNが設定されていません")
        except Exception as e:
            print(f"SNSサービス初期化エラー: {str(e)}")
            self.available = False
    
    async def send_notification(self, contact_form: ContactForm, contact_id: str) -> bool:
        """SNS通知を送信"""
        if not self.available:
            return False
        
        try:
            message = {
                'contact_id': contact_id,
                'name': contact_form.name,
                'email': contact_form.email,
                'subject': contact_form.subject,
                'message': contact_form.message,
                'phone': contact_form.phone,
                'company': contact_form.company,
                'timestamp': datetime.utcnow().isoformat(),
                'reply_to': contact_form.email
            }
            
            self.sns.publish(
                TopicArn=self.topic_arn,
                Message=json.dumps(message, ensure_ascii=False),
                Subject=f"【新しいお問い合わせ】{contact_form.subject}"
            )
            
            print("SNS通知: 送信成功")
            return True
        except Exception as e:
            # ネットワークエラーなどの詳細情報のみログ出力
            error_type = type(e).__name__
            print(f"SNS通知: 送信失敗 ({error_type})")
            if "network" in str(e).lower() or "connection" in str(e).lower() or "timeout" in str(e).lower():
                print(f"ネットワークエラー詳細: {str(e)}")
            return False

class S3Service:
    """Amazon S3保存サービス"""
    def __init__(self):
        try:
            self.is_local = os.getenv('ENVIRONMENT', 'development') == 'development'
            
            if self.is_local:
                # 開発環境: LocalStack設定
                self.s3 = boto3.client(
                    's3',
                    endpoint_url='http://localhost:4566',
                    aws_access_key_id='test',
                    aws_secret_access_key='test',
                    region_name='us-east-1'
                )
                self.bucket_name = 'news-api-contacts'
            else:
                # 本番環境: AWS S3設定
                self.s3 = boto3.client(
                    's3',
                    region_name=os.getenv('AWS_REGION', 'ap-northeast-1'),
                    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
                )
                self.bucket_name = os.getenv('S3_CONTACT_BUCKET_NAME', 'news-api-contacts')
            
            # バケットの存在確認・作成
            self._ensure_bucket_exists()
            self.available = True
        except Exception as e:
            print(f"S3サービス初期化エラー: {str(e)}")
            self.available = False
    
    def _ensure_bucket_exists(self):
        """バケットの存在確認・作成"""
        try:
            self.s3.head_bucket(Bucket=self.bucket_name)
        except:
            try:
                if self.is_local:
                    self.s3.create_bucket(Bucket=self.bucket_name)
                else:
                    self.s3.create_bucket(
                        Bucket=self.bucket_name,
                        CreateBucketConfiguration={
                            'LocationConstraint': os.getenv('AWS_REGION', 'ap-northeast-1')
                        }
                    )
            except Exception as e:
                print(f"バケット作成エラー: {str(e)}")
    
    async def save_contact(self, contact_form: ContactForm, contact_id: str) -> bool:
        """お問い合わせをS3に保存"""
        if not self.available:
            return False
        
        try:
            contact_data = {
                'id': contact_id,
                'name': contact_form.name,
                'email': contact_form.email,
                'subject': contact_form.subject,
                'message': contact_form.message,
                'phone': contact_form.phone,
                'company': contact_form.company,
                'timestamp': datetime.utcnow().isoformat(),
                'status': 'new'
            }
            
            s3_key = f"contacts/{datetime.utcnow().strftime('%Y/%m/%d')}/{contact_id}.json"
            
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=json.dumps(contact_data, ensure_ascii=False, indent=2),
                ContentType='application/json'
            )
            
            print("S3保存: 成功")
            return True
        except Exception as e:
            # ネットワークエラーなどの詳細情報のみログ出力
            error_type = type(e).__name__
            print(f"S3保存: 失敗 ({error_type})")
            if "network" in str(e).lower() or "connection" in str(e).lower() or "timeout" in str(e).lower():
                print(f"ネットワークエラー詳細: {str(e)}")
            return False

class EmailService:
    """統合メール送信サービス"""
    
    def __init__(self):
        try:
            self.config = EmailConfig()
            self.fastmail = FastMail(self.config.conf)
            self.is_local = self.config.is_local
            
            # 各種サービスの初期化
            self.rate_limiter = RateLimiter()
            self.sns_service = SNSService()
            self.s3_service = S3Service()
            
            self.available = True
        except Exception as e:
            print(f"メールサービス初期化エラー: {str(e)}")
            self.available = False
    
    async def check_rate_limit(self, ip: str, email: str) -> bool:
        """レート制限をチェック"""
        # 開発環境ではレート制限を無効化
        if self.is_local:
            return True
        
        # IPアドレスベースの制限（1時間に5回）
        if not await self.rate_limiter.check_rate_limit(f"ip:{ip}", 5, 3600):
            return False
        
        # メールアドレスベースの制限（1時間に3回）
        if not await self.rate_limiter.check_rate_limit(f"email:{email}", 3, 3600):
            return False
        
        return True
    
    async def process_contact_form(
        self, 
        contact_form: ContactForm,
        ip_address: str = None
    ) -> dict:
        """お問い合わせフォームを統合処理（SNS通知のみ）"""
        if not self.available:
            return {
                "success": False,
                "error": "メールサービスが利用できません"
            }
        
        # レート制限チェック
        if ip_address and not await self.check_rate_limit(ip_address, contact_form.email):
            return {
                "success": False,
                "error": "送信制限を超えました。しばらく時間をおいてから再度お試しください。"
            }
        
        try:
            # お問い合わせIDの生成
            contact_id = str(uuid.uuid4())
            
            # 並行処理でS3保存とSNS通知を実行
            results = await asyncio.gather(
                self.s3_service.save_contact(contact_form, contact_id),
                self.sns_service.send_notification(contact_form, contact_id),
                return_exceptions=True
            )
            
            s3_saved, sns_sent = results
            
            # 結果の評価
            success = True
            errors = []
            
            if isinstance(s3_saved, Exception):
                errors.append(f"S3保存エラー: {str(s3_saved)}")
            elif not s3_saved:
                errors.append("S3への保存に失敗しました")
            
            if isinstance(sns_sent, Exception):
                errors.append(f"SNS通知エラー: {str(sns_sent)}")
            elif not sns_sent and not self.is_local:
                errors.append("SNS通知の送信に失敗しました")
            
            return {
                "success": success,
                "contact_id": contact_id,
                "message": "お問い合わせを受け付けました。" + (
                    "SNS通知でお知らせしました。" if not self.is_local 
                    else "開発環境でお問い合わせを受け付けました。"
                ),
                "errors": errors if errors else None
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"お問い合わせの処理に失敗しました: {str(e)}"
            }
    
    async def send_contact_form_email(
        self, 
        contact_form: ContactForm,
        admin_email: str = None
    ) -> bool:
        """従来のメール送信（後方互換性のため）"""
        if not self.available:
            print("メール送信: サービス利用不可")
            return False
            
        try:
            # 管理者宛のメール
            admin_email = admin_email or os.getenv("ADMIN_EMAIL", "admin@example.com")
            
            # お問い合わせ内容を管理者に送信
            admin_message = MessageSchema(
                subject=f"【お問い合わせ】{contact_form.subject}",
                recipients=[admin_email],
                body=self._create_admin_email_body(contact_form),
                subtype=MessageType.html
            )
            
            # メール送信
            await self.fastmail.send_message(admin_message)
            
            print("メール送信: 成功")
            return True
            
        except Exception as e:
            # ネットワークエラーなどの詳細情報のみログ出力
            error_type = type(e).__name__
            print(f"メール送信: 失敗 ({error_type})")
            if "network" in str(e).lower() or "connection" in str(e).lower() or "timeout" in str(e).lower() or "smtp" in str(e).lower():
                print(f"ネットワークエラー詳細: {str(e)}")
            return False
    
    async def send_notification_email(
        self,
        to_email: str,
        subject: str,
        message: str,
        template_name: Optional[str] = None,
        template_data: Optional[dict] = None
    ) -> bool:
        """通知メールを送信"""
        if not self.available:
            print("通知メール: サービス利用不可")
            return False
            
        try:
            email_message = MessageSchema(
                subject=subject,
                recipients=[to_email],
                body=f"<html><body><p>{message}</p></body></html>",
                subtype=MessageType.html
            )
            
            await self.fastmail.send_message(email_message)
            print("通知メール: 送信成功")
            return True
            
        except Exception as e:
            # ネットワークエラーなどの詳細情報のみログ出力
            error_type = type(e).__name__
            print(f"通知メール: 送信失敗 ({error_type})")
            if "network" in str(e).lower() or "connection" in str(e).lower() or "timeout" in str(e).lower() or "smtp" in str(e).lower():
                print(f"ネットワークエラー詳細: {str(e)}")
            return False
    
    def _create_admin_email_body(self, contact_form: ContactForm) -> str:
        """管理者向けメール本文を生成"""
        return f"""
        <html>
        <body>
            <h2>新しいお問い合わせが届きました</h2>
            <table border="1" cellpadding="10" cellspacing="0">
                <tr><td><strong>お名前</strong></td><td>{contact_form.name or '未入力'}</td></tr>
                <tr><td><strong>メールアドレス</strong></td><td>{contact_form.email}</td></tr>
                <tr><td><strong>件名</strong></td><td>{contact_form.subject}</td></tr>
                <tr><td><strong>電話番号</strong></td><td>{contact_form.phone or '未入力'}</td></tr>
                <tr><td><strong>会社名</strong></td><td>{contact_form.company or '未入力'}</td></tr>
            </table>
            <h3>お問い合わせ内容</h3>
            <div style="border: 1px solid #ccc; padding: 10px; background-color: #f9f9f9;">
                {contact_form.message.replace(chr(10), '<br>')}
            </div>
        </body>
        </html>
        """
    
    def health_check(self) -> dict:
        """メールサービスのヘルスチェック"""
        if not self.available:
            return {
                "status": "unavailable",
                "error": "メールサービスの初期化に失敗しました"
            }
        
        health_info = {
            "status": "available",
            "is_local": self.is_local,
            "mail_server": self.config.conf.MAIL_SERVER,
            "mail_port": self.config.conf.MAIL_PORT,
            "template_folder": str(self.config.conf.TEMPLATE_FOLDER),
            "rate_limit_enabled": not self.is_local,  # 開発環境では無効
            "services": {
                "rate_limiter": self.rate_limiter.available,
                "sns": self.sns_service.available,
                "s3": self.s3_service.available
            }
        }
        
        return health_info

# グローバルインスタンス（遅延初期化）
email_service = None

def get_email_service():
    """メールサービスのインスタンスを取得"""
    global email_service
    if email_service is None:
        email_service = EmailService()
    return email_service 