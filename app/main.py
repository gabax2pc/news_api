from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.openapi.utils import get_openapi
from contextlib import asynccontextmanager
from .routers import news, contact
from . import search
import yaml
import json
import re
import logging
import os
from pathlib import Path

# ログ設定
def setup_logging():
    """ログ設定を初期化"""
    # logsディレクトリを作成
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # ログファイルのパス
    log_file = logs_dir / "api.log"
    
    # ログ設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()  # コンソールにも出力
        ]
    )

# ログ設定を初期化
setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 起動時の処理
    search.setup_index()
    yield
    # 終了時の処理（必要に応じて）

app = FastAPI(
    title="News API",
    description="FastAPI + Meilisearchを使用した高速ニュース記事管理API",
    version="1.0.0",
    docs_url="/docs",  # デフォルトのdocsを有効化
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORSの設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では適切に制限してください
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def mask_personal_info(data_str: str) -> str:
    """個人情報をマスクする関数"""
    try:
        # JSONとしてパース
        data = json.loads(data_str)
        
        # 個人情報フィールドをマスク（件名とメッセージは除外）
        sensitive_fields = ['email', 'phone', 'name', 'company']
        
        def mask_value(value):
            if isinstance(value, str) and len(value) > 0:
                # 全ての文字列を完全にマスク
                return '*' * len(value)
            return value
        
        # データをマスク
        if isinstance(data, dict):
            for field, value in data.items():
                if value and isinstance(value, str):
                    # 指定されたフィールドまたはメールアドレスを含む値をマスク
                    if field in sensitive_fields or '@' in value:
                        data[field] = mask_value(value)
        
        return json.dumps(data, ensure_ascii=False)
    except (json.JSONDecodeError, Exception):
        # JSONでない場合は正規表現でマスク
        # メールアドレスを完全にマスク
        def mask_email(match):
            full_email = match.group(0)
            return '*' * len(full_email)
        
        data_str = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', mask_email, data_str)
        
        # 電話番号を完全にマスク
        def mask_phone(match):
            full_phone = match.group(0)
            return '*' * len(full_phone)
        
        data_str = re.sub(r'\d{2,3}-\d{4}-\d{4}', mask_phone, data_str)
        data_str = re.sub(r'\d{3}-\d{4}-\d{4}', mask_phone, data_str)
        return data_str

# リクエストログ用ミドルウェア
@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"リクエスト: {request.method} {request.url}")
    if request.method in ["POST", "PUT", "PATCH"]:
        body = await request.body()
        # バイナリデータの場合は適切に処理
        try:
            if body:
                # Content-Typeをチェック
                content_type = request.headers.get("content-type", "")
                if "multipart/form-data" in content_type:
                    print(f"ボディ: [multipart/form-data - {len(body)} bytes]")
                elif "application/octet-stream" in content_type:
                    print(f"ボディ: [binary data - {len(body)} bytes]")
                else:
                    body_str = body.decode('utf-8')
                    masked_body = mask_personal_info(body_str)
                    print(f"ボディ: {masked_body}")
            else:
                print("ボディ: (空)")
        except UnicodeDecodeError:
            print(f"ボディ: [binary data - {len(body)} bytes]")
    response = await call_next(request)
    return response

# 静的ファイルの配信は廃止（S3を使用）
# import os
# if os.path.exists("static"):
#     app.mount("/static", StaticFiles(directory="static"), name="static")

# ニュース記事のルーターを追加
app.include_router(news.router, prefix="/api/v1/news", tags=["news"])
app.include_router(contact.router, prefix="/api/v1", tags=["contact"])

@app.get("/")
def read_root():
    return {
        "message": "News API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }

# OpenAPI YAML エンドポイント
@app.get("/openapi.yaml", include_in_schema=False)
async def get_openapi_yaml():
    openapi_json = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    yaml_str = yaml.dump(openapi_json, default_flow_style=False, allow_unicode=True)
    return Response(content=yaml_str, media_type="application/x-yaml")

# カスタムOpenAPIスキーマ
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="News API",
        version="1.0.0",
        description="FastAPI + Meilisearchを使用した高速ニュース記事管理API",
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

 