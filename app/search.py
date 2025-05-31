from meilisearch import Client
from meilisearch.index import Index
from datetime import datetime, timezone
import os
from dotenv import load_dotenv
from typing import List, Optional, Dict, Any
import json
import time

load_dotenv()

# Meilisearchクライアントの初期化
client = Client(
    os.getenv("MEILISEARCH_URL", "http://localhost:7700"),
    os.getenv("MEILI_MASTER_KEY")
)

# インデックス設定
INDEX_NAME = "articles"

_id_counter = 1

def get_next_id() -> int:
    global _id_counter
    result = _id_counter
    _id_counter += 1
    return result

def reset_id_counter():
    global _id_counter
    _id_counter = 1

def setup_index():
    """インデックスの設定を行います"""
    index = client.index(INDEX_NAME)
    
    # インデックス設定
    settings = {
        "searchableAttributes": ["title", "content", "category", "author", "tags"],
        "filterableAttributes": ["category", "published", "created_at", "tags"],
        "sortableAttributes": ["created_at", "updated_at"],
        "faceting": {
            "maxValuesPerFacet": 100
        },
        "rankingRules": [
            "words",
            "typo",
            "proximity",
            "attribute",
            "sort",
            "exactness"
        ]
    }
    
    index.update_settings(settings)
    return index

def create_article(article_data: Dict[str, Any]) -> Dict[str, Any]:
    """記事を作成します"""
    index = client.index(INDEX_NAME)
    
    # 現在時刻を取得
    now = datetime.now(timezone.utc)
    
    # 記事データの作成
    article = {
        "id": get_next_id(),
        **article_data,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat()
    }
    
    # インデックスに追加
    task = index.add_documents([article])
    index.wait_for_task(task.task_uid)
    return article

def update_article(article_id: int, article_data: Dict[str, Any]) -> Dict[str, Any]:
    """記事を更新します"""
    index = client.index(INDEX_NAME)
    article = get_article(article_id)
    if not article:
        raise ValueError("記事が見つかりません")
    update_data = {k: v for k, v in article_data.items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    updated_article = {**article, **update_data}
    task = index.update_documents([updated_article])
    index.wait_for_task(task.task_uid)
    # インデックス反映を待つ
    time.sleep(0.1)
    return updated_article

def delete_article(article_id: int):
    """記事を削除します（S3画像も含む）"""
    index = client.index(INDEX_NAME)
    
    # 削除前に記事を取得してサムネイルURLを確認
    article = get_article(article_id)
    if not article:
        raise ValueError("記事が見つかりません")
    
    # S3画像の削除処理
    thumbnail_url = article.get("thumbnail_url")
    if thumbnail_url and _is_s3_thumbnail_url(thumbnail_url):
        try:
            # S3サービスをインポート（循環インポートを避けるため関数内でインポート）
            from .s3_service import s3_service
            
            # S3 URLからファイル名を抽出
            filename = _extract_s3_filename(thumbnail_url)
            if filename:
                print(f"S3画像削除: {filename}")
                success = s3_service.delete_image(filename)
                if success:
                    print(f"S3画像削除: 成功")
                else:
                    print(f"S3画像削除: 失敗（ファイルが存在しない可能性）")
        except Exception as e:
            print(f"S3画像削除: 失敗 ({type(e).__name__}: {str(e)})")
            # S3削除に失敗しても記事削除は続行
    
    # 記事をMeilisearchから削除
    task = index.delete_document(article_id)
    index.wait_for_task(task.task_uid)
    # インデックス反映を待つ
    time.sleep(0.1)
    print(f"記事削除: 完了 (ID: {article_id})")

def _is_s3_thumbnail_url(url: str) -> bool:
    """URLがS3サムネイル画像かどうかを判定"""
    if not url:
        return False
    
    # thumbnailsディレクトリのパスが含まれているかチェック
    if "/thumbnails/" not in url:
        return False
    
    # 追加の安全性チェック：一般的なS3/CDNドメインパターン
    url_lower = url.lower()
    s3_patterns = [
        ".s3.",  # AWS S3直接URL
        ".amazonaws.com",  # AWS S3
        ".cloudfront.net",  # CloudFront
        "localhost:4566",  # LocalStack
    ]
    
    # S3関連のドメインパターンまたはローカル開発環境の場合のみ削除対象とする
    is_s3_domain = any(pattern in url_lower for pattern in s3_patterns)
    
    # 環境変数で設定されたカスタムドメインもチェック
    from dotenv import load_dotenv
    import os
    load_dotenv()
    custom_domain = os.getenv('CLOUDFRONT_DOMAIN')
    if custom_domain and custom_domain.lower() in url_lower:
        is_s3_domain = True
    
    return is_s3_domain

def _extract_s3_filename(url: str) -> Optional[str]:
    """S3 URLからファイル名（パス含む）を抽出"""
    if "/thumbnails/" not in url:
        return None
    
    # /thumbnails/以降の部分を取得
    filename = url.split("/thumbnails/")[-1]
    
    # クエリパラメータがある場合は除去
    if "?" in filename:
        filename = filename.split("?")[0]
    
    # フラグメントがある場合は除去
    if "#" in filename:
        filename = filename.split("#")[0]
    
    return f"thumbnails/{filename}" if filename else None

def get_article(article_id: int) -> Optional[Dict[str, Any]]:
    """記事を取得します"""
    index = client.index(INDEX_NAME)
    try:
        doc = index.get_document(article_id)
        # DocumentオブジェクトをDictに変換
        return dict(doc) if doc else None
    except:
        return None

def list_articles(
    skip: int = 0,
    limit: int = 10,
    category: Optional[str] = None,
    published: Optional[bool] = None,
    tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """記事一覧を取得します"""
    index = client.index(INDEX_NAME)
    
    # フィルター条件の構築
    filters = []
    if category:
        filters.append(f"category = {json.dumps(category)}")
    if published is not None:
        filters.append(f"published = {str(published).lower()}")
    if tags:
        # タグは配列なので、いずれかのタグにマッチする条件を作成
        tag_filters = [f"tags = {json.dumps(tag)}" for tag in tags]
        if tag_filters:
            filters.append(f"({' OR '.join(tag_filters)})")
    
    filter_str = " AND ".join(filters) if filters else None
    
    # 検索実行
    results = index.search(
        "",
        {
            "limit": limit,
            "offset": skip,
            "filter": filter_str,
            "sort": ["created_at:desc"]
        }
    )
    
    return {
        "items": results["hits"],
        "total": results["estimatedTotalHits"],
        "limit": limit,
        "offset": skip
    }

def search_articles(
    query: str,
    category: Optional[str] = None,
    published: Optional[bool] = None,
    tags: Optional[List[str]] = None,
    limit: int = 10,
    offset: int = 0,
    sort_by: Optional[str] = None
) -> Dict[str, Any]:
    """記事を検索します"""
    index = client.index(INDEX_NAME)
    
    # フィルター条件の構築
    filters = []
    if category:
        filters.append(f"category = {json.dumps(category)}")
    if published is not None:
        filters.append(f"published = {str(published).lower()}")
    if tags:
        # タグは配列なので、いずれかのタグにマッチする条件を作成
        tag_filters = [f"tags = {json.dumps(tag)}" for tag in tags]
        if tag_filters:
            filters.append(f"({' OR '.join(tag_filters)})")
    
    filter_str = " AND ".join(filters) if filters else None
    
    # ソート条件の解析
    sort = ["created_at:desc"]  # デフォルト
    if sort_by:
        field, order = sort_by.split(":")
        sort = [f"{field}:{order}"]
    
    # 検索実行
    results = index.search(
        query,
        {
            "limit": limit,
            "offset": offset,
            "filter": filter_str,
            "sort": sort
        }
    )
    
    return {
        "items": results["hits"],
        "total": results["estimatedTotalHits"],
        "limit": limit,
        "offset": offset
    }

def clear_all_articles():
    index = client.index(INDEX_NAME)
    task = index.delete_all_documents()
    index.wait_for_task(task.task_uid)

def get_facet_counts(
    query: Optional[str] = None,
    category: Optional[str] = None,
    published: Optional[bool] = None,
    tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """ファセットカウントを取得します"""
    index = client.index(INDEX_NAME)
    
    # フィルター条件の構築（ファセットカウント用）
    filters = []
    if category:
        filters.append(f"category = {json.dumps(category)}")
    if published is not None:
        filters.append(f"published = {str(published).lower()}")
    if tags:
        # タグは配列なので、いずれかのタグにマッチする条件を作成
        tag_filters = [f"tags = {json.dumps(tag)}" for tag in tags]
        if tag_filters:
            filters.append(f"({' OR '.join(tag_filters)})")
    
    filter_str = " AND ".join(filters) if filters else None
    
    # ファセット検索実行
    results = index.search(
        query or "",
        {
            "limit": 0,  # 結果は不要、ファセットのみ取得
            "filter": filter_str,
            "facets": ["category", "published", "tags"]
        }
    )
    
    # ファセット結果の整形
    facets = results.get("facetDistribution", {})
    
    # カテゴリファセット
    categories = []
    if "category" in facets:
        for value, count in facets["category"].items():
            categories.append({"value": value, "count": count})
        # カウント順でソート
        categories.sort(key=lambda x: x["count"], reverse=True)
    
    # タグファセット
    tags_facet = []
    if "tags" in facets:
        for value, count in facets["tags"].items():
            tags_facet.append({"value": value, "count": count})
        # カウント順でソート
        tags_facet.sort(key=lambda x: x["count"], reverse=True)
    
    # 公開状態ファセット
    published_facet = []
    if "published" in facets:
        for value, count in facets["published"].items():
            # booleanを日本語に変換
            display_value = "公開" if value == "true" else "非公開"
            published_facet.append({"value": display_value, "count": count})
        # 公開を先に表示
        published_facet.sort(key=lambda x: x["value"] == "公開", reverse=True)
    
    return {
        "categories": categories,
        "tags": tags_facet,
        "published": published_facet,
        "total_articles": results.get("estimatedTotalHits", 0)
    } 