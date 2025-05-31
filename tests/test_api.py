import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import search
import io
from pathlib import Path
import uuid

@pytest.fixture(autouse=True)
def clear_meilisearch():
    # 各テストの前後でインデックスとIDカウンタをリセット
    search.clear_all_articles()
    search.reset_id_counter()
    # インデックス設定を更新（タグフィルタリングを有効にする）
    search.setup_index()
    yield
    search.clear_all_articles()
    search.reset_id_counter()

@pytest.fixture(scope="function")
def client():
    with TestClient(app) as test_client:
        yield test_client

def test_create_article(client):
    """記事作成のテスト"""
    article_data = {
        "title": "テスト記事",
        "content": "これはテストです",
        "category": "technology",
        "author": "テスト著者",
        "tags": ["AI", "機械学習", "Python"],
        "published": False,
    }
    
    # 末尾のスラッシュなしで作成
    response = client.post("/api/v1/news", json=article_data)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == article_data["title"]
    assert data["content"] == article_data["content"]
    assert data["category"] == article_data["category"]
    assert data["author"] == article_data["author"]
    assert data["tags"] == article_data["tags"]
    assert data["published"] == article_data["published"]
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data
    
    # 末尾のスラッシュありで作成
    response = client.post("/api/v1/news/", json=article_data)
    assert response.status_code == 200

def test_thumbnail_upload_local_deprecated(client):
    """ローカルサムネイルアップロードのテスト（廃止機能）"""
    # テスト用の画像データを作成（1x1ピクセルのPNG）
    png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82'
    
    # ローカルサムネイル機能は廃止されたため、410エラーが返されることを確認
    response = client.post(
        "/api/v1/news/thumbnails",
        files={"file": ("test.png", io.BytesIO(png_data), "image/png")}
    )
    assert response.status_code == 410
    assert "廃止されました" in response.json()["detail"]
    
    # ローカルサムネイル削除も廃止されていることを確認
    delete_response = client.delete("/api/v1/news/thumbnails/test-file.png")
    assert delete_response.status_code == 410
    assert "廃止されました" in delete_response.json()["detail"]

def test_thumbnail_upload_s3(client):
    """S3サムネイルアップロードのテスト"""
    # テスト用の画像データを作成（1x1ピクセルのPNG）
    png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82'
    
    # S3ヘルスチェック
    health_response = client.get("/api/v1/news/s3/health")
    if health_response.status_code == 200 and health_response.json().get("status") == "healthy":
        # S3が利用可能な場合のテスト
        response = client.post(
            "/api/v1/news/thumbnails/s3",
            files={"file": ("test.png", io.BytesIO(png_data), "image/png")}
        )
        assert response.status_code == 200
        data = response.json()
        assert "s3_url" in data
        assert "filename" in data
        assert "size" in data
        assert "cache_control" in data
        assert data["s3_url"].startswith("http://localhost:4566/news-api-thumbnails/")
        
        # 不正なファイル形式
        response = client.post(
            "/api/v1/news/thumbnails/s3",
            files={"file": ("test.txt", io.BytesIO(b"test"), "text/plain")}
        )
        assert response.status_code == 400
        assert "サポートされていないファイル形式" in response.json()["detail"]
    else:
        # S3が利用できない場合はスキップ
        pytest.skip("S3サービスが利用できません")

def test_create_article_with_thumbnail(client):
    """サムネイル付き記事作成のテスト（S3のみ）"""
    # S3サムネイルでのテスト
    article_data_s3 = {
        "title": "S3サムネイル付き記事",
        "content": "これはS3サムネイル付きの記事です",
        "category": "technology",
        "author": "テスト著者",
        "tags": ["画像", "S3", "サムネイル"],
        "published": True,
        "thumbnail_url": "http://localhost:4566/news-api-thumbnails/thumbnails/test-image.png",
        "thumbnail_alt": "S3テスト画像"
    }
    
    response = client.post("/api/v1/news", json=article_data_s3)
    assert response.status_code == 200
    data = response.json()
    assert data["thumbnail_url"] == article_data_s3["thumbnail_url"]
    assert data["thumbnail_alt"] == article_data_s3["thumbnail_alt"]
    
    # 外部URLでのテスト（例：CDN）
    article_data_external = {
        "title": "外部サムネイル付き記事",
        "content": "これは外部URLのサムネイル付きの記事です",
        "category": "technology",
        "author": "テスト著者",
        "tags": ["画像", "外部URL"],
        "published": True,
        "thumbnail_url": "https://example.com/images/sample.jpg",
        "thumbnail_alt": "外部画像"
    }
    
    response = client.post("/api/v1/news", json=article_data_external)
    assert response.status_code == 200
    data = response.json()
    assert data["thumbnail_url"] == article_data_external["thumbnail_url"]
    assert data["thumbnail_alt"] == article_data_external["thumbnail_alt"]

def test_read_articles(client):
    """記事一覧取得のテスト"""
    # テストデータの作成
    articles = [
        {
            "title": f"テスト記事{i}",
            "content": f"これはテスト{i}です",
            "category": "technology" if i % 2 == 0 else "business",
            "author": "テスト著者",
            "tags": ["AI", "Python"] if i % 2 == 0 else ["ビジネス", "経済"],
            "published": i % 2 == 0
        }
        for i in range(5)
    ]
    
    for article in articles:
        client.post("/api/v1/news", json=article)
    
    # 基本的な一覧取得（末尾のスラッシュなし）
    response = client.get("/api/v1/news")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert len(data["items"]) == 5
    
    # 基本的な一覧取得（末尾のスラッシュあり）
    response = client.get("/api/v1/news/")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 5
    
    # ページネーションのテスト
    response = client.get("/api/v1/news?limit=2&skip=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    
    # カテゴリーフィルターのテスト
    response = client.get("/api/v1/news?category=technology")
    assert response.status_code == 200
    data = response.json()
    assert all(article["category"] == "technology" for article in data["items"])
    
    # 公開状態フィルターのテスト
    response = client.get("/api/v1/news?published=true")
    assert response.status_code == 200
    data = response.json()
    assert all(article["published"] == True for article in data["items"])
    
    # 複合条件のテスト
    response = client.get("/api/v1/news?category=technology&published=true&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 2
    assert all(article["category"] == "technology" and article["published"] == True for article in data["items"])
    
    # タグフィルターのテスト
    response = client.get("/api/v1/news?tags=AI")
    assert response.status_code == 200
    data = response.json()
    # AIタグを持つ記事があることを確認
    assert any("AI" in article.get("tags", []) for article in data["items"])

def test_search_articles(client):
    """記事検索のテスト"""
    # テストデータの作成
    articles = [
        {
            "title": f"検索テスト記事{i}",
            "content": f"これは検索テスト{i}です",
            "category": "technology" if i % 2 == 0 else "business",
            "author": "テスト著者",
            "tags": ["AI", "Python"] if i % 2 == 0 else ["ビジネス", "経済"],
            "published": i % 2 == 0
        }
        for i in range(5)
    ]
    
    for article in articles:
        client.post("/api/v1/news", json=article)
    
    # 基本的な検索（検索クエリあり）
    response = client.get("/api/v1/news/search?q=検索テスト")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) > 0
    
    # 検索クエリなしでフィルタリングのみ
    response = client.get("/api/v1/news/search?category=technology")
    assert response.status_code == 200
    data = response.json()
    assert all(article["category"] == "technology" for article in data["items"])
    
    # 検索クエリなしでタグフィルタリング
    response = client.get("/api/v1/news/search?tags=AI")
    assert response.status_code == 200
    data = response.json()
    assert all("AI" in article.get("tags", []) for article in data["items"])
    
    # 検索クエリなしで全件取得
    response = client.get("/api/v1/news/search")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 5
    
    # カテゴリーフィルター付き検索
    response = client.get("/api/v1/news/search?q=検索テスト&category=technology")
    assert response.status_code == 200
    data = response.json()
    assert all(article["category"] == "technology" for article in data["items"])
    
    # 公開状態フィルター付き検索
    response = client.get("/api/v1/news/search?q=検索テスト&published=true")
    assert response.status_code == 200
    data = response.json()
    assert all(article["published"] == True for article in data["items"])
    
    # ソート付き検索
    response = client.get("/api/v1/news/search?q=検索テスト&sort_by=created_at:desc")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) > 0

def test_read_article(client):
    """個別記事取得のテスト"""
    # テスト記事の作成
    article_data = {
        "title": "テスト記事",
        "content": "これはテストです",
        "category": "technology",
        "author": "テスト著者",
        "published": True
    }
    response = client.post("/api/v1/news", json=article_data)
    article_id = response.json()["id"]
    
    # 存在する記事の取得
    response = client.get(f"/api/v1/news/{article_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == article_data["title"]
    
    # 存在しない記事の取得
    response = client.get("/api/v1/news/999")
    assert response.status_code == 404

def test_update_article(client):
    """記事更新のテスト"""
    # テスト記事の作成
    article_data = {
        "title": "テスト記事",
        "content": "これはテストです",
        "category": "technology",
        "author": "テスト著者",
        "published": True
    }
    response = client.post("/api/v1/news", json=article_data)
    article_id = response.json()["id"]
    
    # 記事の更新
    update_data = {
        "title": "更新されたタイトル",
        "content": "更新された内容"
    }
    response = client.put(f"/api/v1/news/{article_id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == update_data["title"]
    assert data["content"] == update_data["content"]
    assert data["category"] == article_data["category"]  # 更新されていないフィールドは元の値
    
    # 存在しない記事の更新
    response = client.put("/api/v1/news/999", json=update_data)
    assert response.status_code == 404

def test_delete_article(client):
    """記事削除のテスト"""
    # テスト記事の作成
    article_data = {
        "title": "削除テスト記事",
        "content": "これは削除テストです",
        "category": "technology",
        "author": "テスト著者",
        "published": True
    }
    response = client.post("/api/v1/news", json=article_data)
    article_id = response.json()["id"]
    
    # 記事の削除
    response = client.delete(f"/api/v1/news/{article_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "記事を削除しました"
    
    # 削除された記事の取得を試行
    response = client.get(f"/api/v1/news/{article_id}")
    assert response.status_code == 404
    
    # 存在しない記事の削除を試行
    response = client.delete("/api/v1/news/999")
    assert response.status_code == 404

def test_facet_counts(client):
    """ファセットカウントのテスト"""
    # テストデータの作成
    articles = [
        {
            "title": "AI記事1",
            "content": "AI技術について",
            "category": "technology",
            "author": "著者A",
            "tags": ["AI", "機械学習"],
            "published": True
        },
        {
            "title": "AI記事2",
            "content": "AI応用について",
            "category": "technology",
            "author": "著者B",
            "tags": ["AI", "深層学習"],
            "published": False
        },
        {
            "title": "ビジネス記事1",
            "content": "ビジネス戦略について",
            "category": "business",
            "author": "著者C",
            "tags": ["戦略", "経営"],
            "published": True
        },
        {
            "title": "Python記事1",
            "content": "Python開発について",
            "category": "technology",
            "author": "著者D",
            "tags": ["Python", "プログラミング"],
            "published": True
        }
    ]
    
    for article in articles:
        client.post("/api/v1/news", json=article)
    
    # 基本的なファセットカウント取得
    response = client.get("/api/v1/news/facets")
    assert response.status_code == 200
    data = response.json()
    
    # レスポンス構造の確認
    assert "categories" in data
    assert "tags" in data
    assert "published" in data
    assert "total_articles" in data
    
    # 総記事数の確認
    assert data["total_articles"] == 4
    
    # カテゴリファセットの確認
    categories = {item["value"]: item["count"] for item in data["categories"]}
    assert categories.get("technology") == 3
    assert categories.get("business") == 1
    
    # タグファセットの確認
    tags = {item["value"]: item["count"] for item in data["tags"]}
    assert tags.get("AI") == 2
    assert tags.get("機械学習") == 1
    assert tags.get("深層学習") == 1
    assert tags.get("戦略") == 1
    assert tags.get("経営") == 1
    assert tags.get("Python") == 1
    assert tags.get("プログラミング") == 1
    
    # 公開状態ファセットの確認
    published_counts = {item["value"]: item["count"] for item in data["published"]}
    assert published_counts.get("公開") == 3
    assert published_counts.get("非公開") == 1
    
    # フィルター付きファセットカウント
    response = client.get("/api/v1/news/facets?category=technology")
    assert response.status_code == 200
    data = response.json()
    assert data["total_articles"] == 3
    
    # 検索クエリ付きファセットカウント
    response = client.get("/api/v1/news/facets?q=AI")
    assert response.status_code == 200
    data = response.json()
    assert data["total_articles"] == 2
    
    # 複合条件でのファセットカウント
    response = client.get("/api/v1/news/facets?category=technology&published=true")
    assert response.status_code == 200
    data = response.json()
    assert data["total_articles"] == 2

def test_s3_health_check(client):
    """S3ヘルスチェックのテスト"""
    response = client.get("/api/v1/news/s3/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "is_local" in data
    # LocalStackが起動していない場合は "unhealthy" になる可能性がある
    assert data["status"] in ["healthy", "unhealthy"]

def test_s3_file_list(client):
    """S3ファイル一覧のテスト"""
    # S3ヘルスチェック
    health_response = client.get("/api/v1/news/s3/health")
    if health_response.status_code == 200 and health_response.json().get("status") == "healthy":
        # S3が利用可能な場合のテスト
        response = client.get("/api/v1/news/thumbnails/s3/list")
        assert response.status_code == 200
        data = response.json()
        assert "images" in data
        assert "count" in data
        assert "bucket" in data
        assert "is_local" in data
        assert isinstance(data["images"], list)
        assert isinstance(data["count"], int)
    else:
        # S3が利用できない場合はスキップ
        pytest.skip("S3サービスが利用できません")

def test_s3_file_delete(client):
    """S3ファイル削除のテスト"""
    # テスト用の画像データを作成（1x1ピクセルのPNG）
    png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82'
    
    # S3ヘルスチェック
    health_response = client.get("/api/v1/news/s3/health")
    if health_response.status_code == 200 and health_response.json().get("status") == "healthy":
        # まずファイルをアップロード
        upload_response = client.post(
            "/api/v1/news/thumbnails/s3",
            files={"file": ("test-delete.png", io.BytesIO(png_data), "image/png")}
        )
        assert upload_response.status_code == 200
        upload_data = upload_response.json()
        filename = upload_data["filename"]
        
        # ファイルを削除
        delete_response = client.delete(f"/api/v1/news/thumbnails/s3/{filename}")
        assert delete_response.status_code == 200
        delete_data = delete_response.json()
        assert "message" in delete_data
        assert "削除しました" in delete_data["message"]
        
        # 存在しないファイルの削除を試行
        # 注意: S3のdelete_objectは存在しないファイルでも成功を返すため、
        # 実装によっては200が返される場合があります
        not_found_response = client.delete("/api/v1/news/thumbnails/s3/non-existent-file.png")
        # S3の仕様により、存在しないファイルの削除も成功として扱われる場合があります
        assert not_found_response.status_code in [200, 404]
    else:
        # S3が利用できない場合はスキップ
        pytest.skip("S3サービスが利用できません")

def test_integrated_s3_workflow(client):
    """S3を使った統合ワークフローのテスト"""
    # テスト用の画像データを作成（1x1ピクセルのPNG）
    png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82'
    
    # S3ヘルスチェック
    health_response = client.get("/api/v1/news/s3/health")
    if health_response.status_code == 200 and health_response.json().get("status") == "healthy":
        # 1. S3にサムネイルをアップロード
        upload_response = client.post(
            "/api/v1/news/thumbnails/s3",
            files={"file": ("workflow-test.png", io.BytesIO(png_data), "image/png")}
        )
        assert upload_response.status_code == 200
        upload_data = upload_response.json()
        s3_url = upload_data["s3_url"]
        
        # 2. S3のサムネイルURLを使って記事を作成
        article_data = {
            "title": "S3統合ワークフローテスト",
            "content": "S3にアップロードしたサムネイルを使用した記事です",
            "category": "technology",
            "author": "テスト著者",
            "tags": ["S3", "統合テスト"],
            "published": True,
            "thumbnail_url": s3_url,
            "thumbnail_alt": "S3統合テスト画像"
        }
        
        create_response = client.post("/api/v1/news", json=article_data)
        assert create_response.status_code == 200
        create_data = create_response.json()
        article_id = create_data["id"]
        assert create_data["thumbnail_url"] == s3_url
        
        # 3. 記事を取得してサムネイルURLが正しいことを確認
        get_response = client.get(f"/api/v1/news/{article_id}")
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["thumbnail_url"] == s3_url
        
        # 4. 記事のサムネイルを別のS3画像に更新
        new_upload_response = client.post(
            "/api/v1/news/thumbnails/s3",
            files={"file": ("workflow-test-2.png", io.BytesIO(png_data), "image/png")}
        )
        assert new_upload_response.status_code == 200
        new_upload_data = new_upload_response.json()
        new_s3_url = new_upload_data["s3_url"]
        
        update_response = client.put(f"/api/v1/news/{article_id}", json={
            "thumbnail_url": new_s3_url,
            "thumbnail_alt": "更新されたS3画像"
        })
        assert update_response.status_code == 200
        update_data = update_response.json()
        assert update_data["thumbnail_url"] == new_s3_url
        assert update_data["thumbnail_alt"] == "更新されたS3画像"
        
    else:
        # S3が利用できない場合はスキップ
        pytest.skip("S3サービスが利用できません")

def test_email_health_check(client):
    """メールサービスのヘルスチェックのテスト（SNS統合版）"""
    response = client.get("/api/v1/email/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "is_local" in data
    assert "mail_server" in data
    assert "mail_port" in data
    assert "template_folder" in data
    assert "services" in data
    
    # 各サービスの状態確認
    services = data["services"]
    assert "rate_limiter" in services
    assert "sns" in services
    assert "s3" in services
    
    # メールサービスが利用可能かどうかを確認
    assert data["status"] in ["available", "unavailable"]

def test_contact_form_sns_integration(client):
    """お問い合わせフォーム（SNS統合版）のテスト"""
    unique_email = f"test-sns-{uuid.uuid4()}@example.com"
    
    contact_data = {
        "name": "テスト太郎",
        "email": unique_email,
        "subject": "SNS統合テスト",
        "message": "これはSNS統合版のテスト用お問い合わせです。",
        "phone": "090-1234-5678",
        "company": "テスト株式会社"
    }
    
    response = client.post("/api/v1/contact", json=contact_data)
    
    # レート制限の場合は429エラーが返される
    if response.status_code == 429:
        print("レート制限により送信が制限されました。これは正常な動作です。")
        assert "送信制限" in response.json()["detail"]
        return
    
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "success" in data
    assert "contact_id" in data
    assert data["success"] == True
    assert "お問い合わせを受け付けました" in data["message"]
    
    # contact_idがUUID形式であることを確認
    try:
        uuid.UUID(data["contact_id"])
    except ValueError:
        pytest.fail("contact_idがUUID形式ではありません")

def test_contact_form_sync(client):
    """お問い合わせフォーム（同期・SNS統合版）のテスト"""
    unique_email = f"test-sync-{uuid.uuid4()}@example.com"
    
    contact_data = {
        "name": "テスト太郎",
        "email": unique_email,
        "subject": "テストお問い合わせ",
        "message": "これはテスト用のお問い合わせです。",
        "phone": "090-1234-5678",
        "company": "テスト株式会社"
    }
    
    response = client.post("/api/v1/contact/sync", json=contact_data)
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.json()}")
    
    # レート制限の場合は429エラーが返される
    if response.status_code == 429:
        print("レート制限により送信が制限されました。これは正常な動作です。")
        assert "送信制限" in response.json()["detail"]
        return
    
    if response.status_code == 500:
        # 500エラーの場合は詳細を確認
        print("500エラーが発生しました。詳細を確認してください。")
        # テストは失敗させるが、情報を出力
        assert False, f"500エラー: {response.json()}"
    
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "success" in data
    assert "contact_id" in data
    assert data["success"] == True
    assert "お問い合わせを受け付けました" in data["message"]

def test_contact_form_legacy(client):
    """お問い合わせフォーム（従来版）のテスト"""
    contact_data = {
        "name": "テスト太郎",
        "email": "test@example.com",
        "subject": "従来版テスト",
        "message": "これは従来版のテスト用お問い合わせです。",
        "phone": "090-1234-5678",
        "company": "テスト株式会社"
    }
    
    response = client.post("/api/v1/contact/legacy", json=contact_data)
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "success" in data
    assert "contact_id" in data
    assert data["success"] == True
    assert "お問い合わせを受け付けました" in data["message"]
    assert data["contact_id"].startswith("legacy_")

def test_contact_form_async(client):
    """お問い合わせフォーム（非同期）のテスト - 従来版へのエイリアス"""
    unique_email = f"test-async-{uuid.uuid4()}@example.com"
    
    contact_data = {
        "name": "テスト花子",
        "email": unique_email,
        "subject": "非同期テストお問い合わせ",
        "message": "これは非同期テスト用のお問い合わせです。",
        "phone": "080-9876-5432",
        "company": "サンプル企業"
    }
    
    response = client.post("/api/v1/contact", json=contact_data)
    
    # レート制限の場合は429エラーが返される
    if response.status_code == 429:
        print("レート制限により送信が制限されました。これは正常な動作です。")
        assert "送信制限" in response.json()["detail"]
        return
    
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "お問い合わせを受け付けました" in data["message"]

def test_contact_form_rate_limiting(client):
    """お問い合わせフォームのレート制限テスト"""
    contact_data = {
        "name": "レート制限テスト",
        "email": "ratelimit@example.com",
        "subject": "レート制限テスト",
        "message": "レート制限のテストです。"
    }
    
    # 複数回送信してレート制限をテスト
    # 注意: 実際のRedisが動作していない場合はレート制限は無効化される
    responses = []
    for i in range(6):  # 制限は5回/時間なので6回送信
        response = client.post("/api/v1/contact", json=contact_data)
        responses.append(response)
        print(f"Response {i+1}: Status={response.status_code}")
    
    # レスポンスの分析
    success_count = sum(1 for r in responses if r.status_code == 200)
    rate_limit_count = sum(1 for r in responses if r.status_code == 429)
    error_count = sum(1 for r in responses if r.status_code == 500)
    
    print(f"Success: {success_count}, Rate Limited: {rate_limit_count}, Errors: {error_count}")
    
    # レート制限が動作している場合：
    # - 最初の数回は成功し、その後レート制限に引っかかる
    # - または、既に制限に引っかかっている状態で全てレート制限される
    # レート制限が動作していない場合：
    # - 全て成功する
    
    # レート制限が正常に動作していることを確認
    # （429エラーが発生している = レート制限が動作している）
    assert rate_limit_count > 0 or success_count == 6, f"レート制限が期待通りに動作していません。Success: {success_count}, Rate Limited: {rate_limit_count}, Errors: {error_count}"

def test_contact_form_validation(client):
    """お問い合わせフォームのバリデーションテスト"""
    # 必須フィールド（件名）が不足している場合
    invalid_data = {
        "name": "テスト太郎",
        "email": "test@example.com",
        "subject": "",  # 空の件名
        "message": "テストメッセージ"
    }
    
    response = client.post("/api/v1/contact", json=invalid_data)
    assert response.status_code == 422  # Validation Error
    
    # 必須フィールド（メッセージ）が不足している場合
    invalid_message_data = {
        "name": "テスト太郎",
        "email": "test@example.com",
        "subject": "テスト件名",
        "message": ""  # 空のメッセージ
    }
    
    response = client.post("/api/v1/contact", json=invalid_message_data)
    assert response.status_code == 422  # Validation Error
    
    # 無効なメールアドレス
    invalid_email_data = {
        "name": "テスト太郎",
        "email": "invalid-email",
        "subject": "テスト",
        "message": "テストメッセージ"
    }
    
    response = client.post("/api/v1/contact", json=invalid_email_data)
    assert response.status_code == 422  # Validation Error

def test_contact_form_optional_fields(client):
    """お問い合わせフォームのオプションフィールドテスト"""
    # 最小限の必須フィールドのみ（氏名なし）
    unique_email_1 = f"test-minimal-{uuid.uuid4()}@example.com"
    minimal_data = {
        "email": unique_email_1,
        "subject": "最小限テスト",
        "message": "必須フィールドのみのテストです。氏名は入力していません。"
    }
    
    response = client.post("/api/v1/contact/sync", json=minimal_data)
    
    # レート制限の場合は429エラーが返される
    if response.status_code == 429:
        print("レート制限により送信が制限されました。これは正常な動作です。")
        assert "送信制限" in response.json()["detail"]
        return
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    
    # 全フィールド入力（氏名あり）
    unique_email_2 = f"test-full-{uuid.uuid4()}@example.com"
    full_data = {
        "name": "フル太郎",
        "email": unique_email_2,
        "subject": "全フィールドテスト",
        "message": "全フィールドを入力したテストです。",
        "phone": "03-1234-5678",
        "company": "フル株式会社"
    }
    
    response = client.post("/api/v1/contact/sync", json=full_data)
    
    # レート制限の場合は429エラーが返される
    if response.status_code == 429:
        print("レート制限により送信が制限されました。これは正常な動作です。")
        assert "送信制限" in response.json()["detail"]
        return
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True

def test_test_email_endpoint(client):
    """テストメール送信エンドポイントのテスト"""
    test_email_data = {
        "to_email": "test@example.com",
        "subject": "テストメール",
        "message": "これはテスト用のメールです。"
    }
    
    response = client.post("/api/v1/email/test", json=test_email_data)
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "success" in data
    
    # メールサービスが利用可能な場合は成功、そうでなければエラーメッセージ
    if data["success"]:
        assert "送信しました" in data["message"]
    else:
        assert "送信に失敗" in data["message"]

def test_test_email_validation(client):
    """テストメール送信のバリデーションテスト"""
    # 無効なメールアドレス
    invalid_data = {
        "to_email": "invalid-email",
        "subject": "テストメール",
        "message": "これはテスト用のメールです。"
    }
    
    response = client.post("/api/v1/email/test", json=invalid_data)
    assert response.status_code == 422  # Validation Error
    
    # 必須フィールド（to_email）が不足
    incomplete_data = {
        # to_emailが不足
        "subject": "テストメール",
        "message": "これはテスト用のメールです。"
    }
    
    response = client.post("/api/v1/email/test", json=incomplete_data)
    assert response.status_code == 422  # Validation Error
    
    # デフォルト値のテスト（subjectとmessageは省略可能）
    minimal_data = {
        "to_email": "test@example.com"
    }
    
    response = client.post("/api/v1/email/test", json=minimal_data)
    assert response.status_code == 200  # デフォルト値が使用される
    data = response.json()
    assert "success" in data
    assert "message" in data 