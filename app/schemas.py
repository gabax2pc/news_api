from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List, Dict

class NewsArticle(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    title: str
    content: str
    category: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = []
    published: bool = False
    thumbnail_url: Optional[str] = None  # サムネイルURL
    thumbnail_alt: Optional[str] = None  # サムネイルのalt属性
    created_at: datetime
    updated_at: datetime

class NewsArticleCreate(BaseModel):
    title: str
    content: str
    category: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = []
    published: bool = False
    thumbnail_url: Optional[str] = None
    thumbnail_alt: Optional[str] = None

class NewsArticleUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    author: Optional[str] = None
    tags: Optional[List[str]] = None
    published: Optional[bool] = None
    thumbnail_url: Optional[str] = None
    thumbnail_alt: Optional[str] = None

class SearchResponse(BaseModel):
    items: List[NewsArticle]
    total: int
    limit: int
    offset: int

class FacetCount(BaseModel):
    """ファセットカウントの結果"""
    value: str
    count: int

class FacetResponse(BaseModel):
    """ファセットカウントのレスポンス"""
    categories: List[FacetCount] = []
    tags: List[FacetCount] = []
    published: List[FacetCount] = []
    total_articles: int = 0

class ThumbnailUploadResponse(BaseModel):
    """サムネイルアップロードのレスポンス"""
    thumbnail_url: str
    filename: str
    size: int

class S3UploadResponse(BaseModel):
    """S3アップロードのレスポンス"""
    s3_url: str
    cloudfront_url: Optional[str] = None
    filename: str
    size: int
    cache_control: str 