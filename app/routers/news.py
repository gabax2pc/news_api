from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from typing import List, Optional
import uuid
from pathlib import Path
from .. import schemas, search

# S3サービスのインポート（オプション）
try:
    from ..s3_service import s3_service
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False

router = APIRouter()

# ローカルサムネイル機能は廃止
# THUMBNAIL_DIR = Path("static/thumbnails")
# THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)

# 許可する画像形式
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

@router.get("/s3/health")
def check_s3_health():
    """S3サービスのヘルスチェック"""
    if not S3_AVAILABLE:
        return {"status": "unavailable", "message": "S3サービスが利用できません"}
    
    return s3_service.health_check()

@router.post("/thumbnails/s3", response_model=schemas.S3UploadResponse)
async def upload_thumbnail_to_s3(
    file: UploadFile = File(...),
    cache_duration: str = Query("long", description="キャッシュ期間: short, medium, long")
):
    """S3にサムネイル画像をアップロードします"""
    
    if not S3_AVAILABLE:
        raise HTTPException(status_code=503, detail="S3サービスが利用できません")
    
    # ファイルタイプの検証
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400, 
            detail=f"サポートされていないファイル形式です。許可される形式: {', '.join(ALLOWED_IMAGE_TYPES)}"
        )
    
    # ファイルサイズの検証
    file_content = await file.read()
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"ファイルサイズが大きすぎます。最大サイズ: {MAX_FILE_SIZE // (1024*1024)}MB"
        )
    
    try:
        # S3にアップロード
        s3_url, cloudfront_url, filename = s3_service.upload_image(
            file_content=file_content,
            content_type=file.content_type,
            original_filename=file.filename,
            cache_duration=cache_duration
        )
        
        return schemas.S3UploadResponse(
            s3_url=s3_url,
            cloudfront_url=cloudfront_url,
            filename=filename,
            size=len(file_content),
            cache_control=s3_service.cache_settings.get(cache_duration, s3_service.cache_settings['long'])
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/thumbnails/s3/list")
def list_s3_thumbnails(
    prefix: str = Query("thumbnails/", description="検索プレフィックス"),
    max_keys: int = Query(100, description="最大取得件数")
):
    """S3バケット内のサムネイル一覧を取得"""
    
    if not S3_AVAILABLE:
        raise HTTPException(status_code=503, detail="S3サービスが利用できません")
    
    try:
        images = s3_service.list_images(prefix=prefix, max_keys=max_keys)
        return {
            "images": images,
            "count": len(images),
            "bucket": s3_service.bucket_name,
            "is_local": s3_service.is_local
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/thumbnails/s3/{filename:path}")
def delete_s3_thumbnail(filename: str):
    """S3からサムネイル画像を削除します"""
    
    if not S3_AVAILABLE:
        raise HTTPException(status_code=503, detail="S3サービスが利用できません")
    
    try:
        success = s3_service.delete_image(filename)
        if success:
            return {"message": "S3からサムネイルを削除しました", "filename": filename}
        else:
            raise HTTPException(status_code=404, detail="ファイルが見つかりません")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/thumbnails")
async def upload_thumbnail_deprecated(file: UploadFile = File(...)):
    """ローカルサムネイルアップロード（廃止済み）"""
    raise HTTPException(
        status_code=410, 
        detail="ローカルサムネイル機能は廃止されました。/api/v1/news/thumbnails/s3 を使用してください。"
    )

@router.delete("/thumbnails/{filename}")
def delete_thumbnail_deprecated(filename: str):
    """ローカルサムネイル削除（廃止済み）"""
    raise HTTPException(
        status_code=410, 
        detail="ローカルサムネイル機能は廃止されました。/api/v1/news/thumbnails/s3/{filename} を使用してください。"
    )

@router.post("", response_model=schemas.NewsArticle)
def create_article(article: schemas.NewsArticleCreate):
    """新しい記事を作成します"""
    try:
        return search.create_article(article.model_dump())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("", response_model=schemas.SearchResponse)
def read_articles(
    skip: int = 0,
    limit: int = 10,
    category: Optional[str] = None,
    published: Optional[bool] = None,
    tags: Optional[List[str]] = Query(None, description="タグでフィルタリング（複数指定可能）")
):
    """記事一覧を取得します"""
    return search.list_articles(skip, limit, category, published, tags)

@router.get("/facets", response_model=schemas.FacetResponse)
def get_facets(
    q: Optional[str] = Query(None, description="検索クエリ（任意）"),
    category: Optional[str] = Query(None, description="カテゴリでフィルタリング"),
    published: Optional[bool] = Query(None, description="公開状態でフィルタリング"),
    tags: Optional[List[str]] = Query(None, description="タグでフィルタリング（複数指定可能）")
):
    """ファセットカウントを取得します（カテゴリ、タグ、公開状態ごとの記事数）"""
    return search.get_facet_counts(
        query=q,
        category=category,
        published=published,
        tags=tags
    )

@router.get("/search", response_model=schemas.SearchResponse)
def search_articles_endpoint(
    q: Optional[str] = Query(None, description="検索クエリ（任意）"),
    category: Optional[str] = Query(None, description="カテゴリでフィルタリング"),
    published: Optional[bool] = Query(None, description="公開状態でフィルタリング"),
    tags: Optional[List[str]] = Query(None, description="タグでフィルタリング（複数指定可能）"),
    limit: int = Query(10, description="取得件数"),
    offset: int = Query(0, description="スキップ件数"),
    sort_by: Optional[str] = Query(None, description="ソート順（例：created_at:desc）")
):
    """記事を検索します（検索クエリなしでフィルタリングのみも可能）"""
    return search.search_articles(
        query=q or "",  # qがNoneの場合は空文字列を渡す
        category=category,
        published=published,
        tags=tags,
        limit=limit,
        offset=offset,
        sort_by=sort_by
    )

@router.get("/{article_id}", response_model=schemas.NewsArticle)
def read_article(article_id: int):
    """指定されたIDの記事を取得します"""
    article = search.get_article(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="記事が見つかりません")
    return article

@router.put("/{article_id}", response_model=schemas.NewsArticle)
def update_article(
    article_id: int,
    article: schemas.NewsArticleUpdate
):
    """指定されたIDの記事を更新します"""
    try:
        return search.update_article(article_id, article.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{article_id}")
def delete_article(article_id: int):
    """指定されたIDの記事を削除します"""
    try:
        search.delete_article(article_id)
        return {"message": "記事を削除しました"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 