from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from ..email_service import get_email_service, ContactForm
import logging

router = APIRouter()

class ContactResponse(BaseModel):
    """お問い合わせレスポンス"""
    success: bool
    message: str
    contact_id: Optional[str] = None
    errors: Optional[list] = None

class EmailHealthResponse(BaseModel):
    """メールサービスヘルスチェックレスポンス"""
    status: str
    is_local: Optional[bool] = None
    mail_server: Optional[str] = None
    mail_port: Optional[int] = None
    template_folder: Optional[str] = None
    services: Optional[Dict[str, bool]] = None
    error: Optional[str] = None

class TestEmailRequest(BaseModel):
    """テストメール送信リクエスト"""
    to_email: EmailStr
    subject: str = "テストメール"
    message: str = "これはテストメールです。"

class TestEmailResponse(BaseModel):
    """テストメール送信レスポンス"""
    success: bool
    message: str

@router.post("/contact", response_model=ContactResponse)
async def submit_contact_form(
    contact_form: ContactForm,
    request: Request
):
    """
    お問い合わせフォームを送信します（SNS統合版）
    
    - **name**: お名前（必須）
    - **email**: メールアドレス（必須）
    - **subject**: 件名（必須）
    - **message**: お問い合わせ内容（必須）
    - **phone**: 電話番号（任意）
    - **company**: 会社名（任意）
    
    機能:
    - S3への保存
    - SNS通知（本番環境のみ）
    - 自動返信メール
    - レート制限
    """
    try:
        email_service = get_email_service()
        
        # IPアドレスの取得
        ip_address = request.client.host
        
        # 統合処理を実行
        result = await email_service.process_contact_form(
            contact_form=contact_form,
            ip_address=ip_address
        )
        
        if result["success"]:
            return ContactResponse(
                success=True,
                message=result["message"],
                contact_id=result["contact_id"],
                errors=result.get("errors")
            )
        else:
            # レート制限やその他のエラー
            if "送信制限" in result["error"]:
                raise HTTPException(
                    status_code=429,
                    detail=result["error"]
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=result["error"]
                )
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"お問い合わせ送信エラー: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="お問い合わせの送信に失敗しました。しばらく時間をおいて再度お試しください。"
        )

@router.post("/contact/legacy", response_model=ContactResponse)
async def submit_contact_form_legacy(
    contact_form: ContactForm,
    background_tasks: BackgroundTasks
):
    """
    お問い合わせフォームを送信します（従来版・後方互換性のため）
    
    - **name**: お名前（必須）
    - **email**: メールアドレス（必須）
    - **subject**: 件名（必須）
    - **message**: お問い合わせ内容（必須）
    - **phone**: 電話番号（任意）
    - **company**: 会社名（任意）
    """
    try:
        email_service = get_email_service()
        
        # バックグラウンドでメール送信を実行
        background_tasks.add_task(
            email_service.send_contact_form_email,
            contact_form
        )
        
        return ContactResponse(
            success=True,
            message="お問い合わせを受け付けました。自動返信メールをご確認ください。",
            contact_id=f"legacy_{hash(contact_form.email + contact_form.subject)}"
        )
        
    except Exception as e:
        logging.error(f"お問い合わせ送信エラー: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="お問い合わせの送信に失敗しました。しばらく時間をおいて再度お試しください。"
        )

@router.post("/contact/sync", response_model=ContactResponse)
async def submit_contact_form_sync(
    contact_form: ContactForm,
    request: Request
):
    """
    お問い合わせフォームを同期的に送信します（テスト用・SNS統合版）
    
    開発・テスト環境でメール送信の結果を即座に確認したい場合に使用
    """
    try:
        email_service = get_email_service()
        
        # IPアドレスの取得
        ip_address = request.client.host
        
        # 統合処理を実行
        result = await email_service.process_contact_form(
            contact_form=contact_form,
            ip_address=ip_address
        )
        
        if result["success"]:
            return ContactResponse(
                success=True,
                message=result["message"],
                contact_id=result["contact_id"],
                errors=result.get("errors")
            )
        else:
            # レート制限やその他のエラー
            if "送信制限" in result["error"]:
                raise HTTPException(
                    status_code=429,
                    detail=result["error"]
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=result["error"]
                )
            
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"お問い合わせ送信エラー: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="お問い合わせの送信に失敗しました。しばらく時間をおいて再度お試しください。"
        )

@router.get("/email/health", response_model=EmailHealthResponse)
def check_email_health():
    """
    メールサービスのヘルスチェック
    
    メール機能が正常に動作するかを確認します
    """
    try:
        email_service = get_email_service()
        health_info = email_service.health_check()
        return EmailHealthResponse(**health_info)
    except Exception as e:
        return EmailHealthResponse(
            status="error",
            error=f"メールサービスのヘルスチェックに失敗しました: {str(e)}"
        )

@router.post("/email/test", response_model=TestEmailResponse)
async def send_test_email(request: TestEmailRequest):
    """
    テストメールを送信します（開発用）
    
    メール機能の動作確認用エンドポイント
    """
    try:
        email_service = get_email_service()
        success = await email_service.send_notification_email(
            to_email=request.to_email,
            subject=request.subject,
            message=request.message
        )
        
        if success:
            return TestEmailResponse(
                success=True, 
                message="テストメールを送信しました"
            )
        else:
            return TestEmailResponse(
                success=False,
                message="テストメール送信に失敗しました"
            )
            
    except Exception as e:
        logging.error(f"テストメール送信エラー: {str(e)}")
        return TestEmailResponse(
            success=False,
            message=f"テストメール送信に失敗しました: {str(e)}"
        ) 