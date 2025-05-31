import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.email_service import get_email_service, ContactForm

def mask_result(result):
    """テスト結果から個人情報をマスクする"""
    if isinstance(result, dict):
        masked_result = result.copy()
        # 個人情報フィールドを完全にマスク（件名とメッセージは除外）
        sensitive_fields = ['email', 'phone', 'name', 'company']
        for field in sensitive_fields:
            if field in masked_result and isinstance(masked_result[field], str):
                masked_result[field] = '*' * len(masked_result[field])
        return masked_result
    return result

async def test_email():
    """メール機能の手動テスト
    
    使用方法:
    cd tests
    python manual_email_test.py
    """
    service = get_email_service()
    print(f'メールサービス利用可能: {service.available}')
    print(f'開発環境: {service.is_local}')
    print(f'レート制限有効: {not service.is_local}')
    print(f'SNSサービス利用可能: {service.sns_service.available}')
    print(f'S3サービス利用可能: {service.s3_service.available}')
    
    # ヘルスチェック
    health = service.health_check()
    print(f'ヘルスチェック: {health}')
    
    # テスト用お問い合わせ（氏名なし）
    contact = ContactForm(
        email='test@example.com',
        subject='SNS通知テスト',
        message='SNS通知のテストです。氏名は必須項目ではありません。'
    )
    
    result = await service.process_contact_form(contact, '127.0.0.1')
    masked_result = mask_result(result)
    print(f'結果: {masked_result}')
    
    # 氏名ありのテストも実行
    print('\n--- 氏名ありのテスト ---')
    contact_with_name = ContactForm(
        name='テスト太郎',
        email='test2@example.com',
        subject='氏名ありテスト',
        message='氏名ありのテストです。'
    )
    
    result2 = await service.process_contact_form(contact_with_name, '127.0.0.1')
    masked_result2 = mask_result(result2)
    print(f'結果: {masked_result2}')

if __name__ == "__main__":
    asyncio.run(test_email()) 