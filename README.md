# News API

FastAPI + Meilisearch + Amazon SNSを使用した高速ニュース記事管理API

## 🚀 特徴

- **高速検索**: Meilisearchによる高速全文検索
- **CRUD操作**: 記事の作成、取得、更新、削除
- **高度な検索**: カテゴリ、公開状態、キーワードでの絞り込み
- **ページネーション**: 大量データの効率的な取得
- **ソート機能**: 作成日時、更新日時での並び替え
- **ファセットカウント**: カテゴリ、タグ、公開状態ごとの記事数集計
- **サムネイル管理**: AWS S3による画像管理（JPEG, PNG, WebP, GIF対応）
- **SNS統合メール機能**: Amazon SNS + S3 + Redis統合のお問い合わせシステム
- **レート制限**: IP・メールアドレス別の送信制限
- **プライバシー保護**: ログ出力時の個人情報自動マスク機能
- **自動ドキュメント**: Swagger UI / ReDoc対応
- **包括的テスト**: 全機能のテストカバレッジ

## 🛠️ 技術スタック

### Backend
- **FastAPI**: 高性能なPython Webフレームワーク
- **Meilisearch**: 高速全文検索エンジン
- **Pydantic**: データバリデーション
- **Redis**: レート制限・セッション管理

### AWS統合
- **Amazon SNS**: リアルタイム通知
- **Amazon S3**: ファイルストレージ（サムネイル・お問い合わせ保存）
- **AWS SES**: メール送信（本番環境推奨）

### パッケージ管理・テスト
- **Pipenv**: 依存関係管理
- **pytest**: テストフレームワーク

## 📦 セットアップ

### 1. リポジトリのクローン
```bash
git clone <repository-url>
cd news_api
```

### 必要なパッケージインストール
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3-pip python3-venv redis-server

# CentOS/RHEL
sudo yum install -y python3-pip redis

# python 依存関係のインストール
pipenv install
```

### 3. 環境変数の設定
```bash
cp env.example .env
```

#### 開発環境用の設定
`.env`ファイルを以下のように編集：
```bash
# 開発環境設定
ENVIRONMENT=development

# Meilisearch設定（開発用）
MEILISEARCH_URL=http://localhost:7700
MEILI_MASTER_KEY=your_password
```

#### 本番環境用の設定
`.env`ファイルを編集
```bash
# AWS設定
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=ap-northeast-1

# S3設定
S3_BUCKET_NAME=your-thumbnails-bucket
S3_CONTACT_BUCKET_NAME=your-contact-bucket
CLOUDFRONT_URL=https://your-cloudfront-domain.cloudfront.net

# SNS設定
SNS_TOPIC_ARN=arn:aws:sns:ap-northeast-1:123456789012:contact-notifications

# メール設定
SMTP_SERVER=email-smtp.ap-northeast-1.amazonaws.com
SMTP_PORT=587
SMTP_USERNAME=your-ses-username
SMTP_PASSWORD=your-ses-password
FROM_EMAIL=noreply@yourdomain.com

# Redis設定
REDIS_URL=redis://localhost:6379

# Meilisearch設定
MEILISEARCH_URL=http://localhost:7700
MEILI_MASTER_KEY=your-production-key

# 環境設定
ENVIRONMENT=production
```

### 4. 環境別の起動方法

#### 🔧 開発環境
```bash
# 開発用サービスを起動（LocalStack、Redis、Meilisearch、MailHog）
docker-compose -f docker-compose.dev.yml up -d

# APIサーバーを起動（ホットリロード有効）
pipenv run uvicorn app.main:app --reload
```

#### 🚀 本番環境
```bash
# 本番用サービスを起動（Redis、Meilisearch）
docker-compose -f docker-compose.prod.yml up -d

# APIサーバーを起動（Gunicorn + Uvicorn Workers）
pipenv run gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

#### 🧪 テスト実行
```bash
# 基本的なサンプル記事を生成
pipenv run python scripts/create_sample_articles.py

# サムネイル付きサンプル記事を生成
pipenv run python scripts/create_sample_articles_with_thumbnails.py

# 全テスト実行
pipenv run pytest

# メール機能のみテスト
pipenv run pytest tests/test_api.py -k "contact_form or email" -v

# 特定のテスト実行
pipenv run pytest tests/test_api.py::test_contact_form_sns_integration -v

# 手動メールテスト
pipenv run python tests/manual_email_test.py
```

### テスト実行結果
- ✅ **20個のテストが成功**
- ✅ **SNS統合機能**: 正常動作
- ✅ **レート制限**: IP・メール別制限
- ✅ **S3統合**: ファイルアップロード・削除
- ✅ **お問い合わせ機能**: SNS通知・S3保存
- ✅ **記事管理**: CRUD・検索・ファセット

### 主要テスト項目
- 記事のCRUD操作
- 高度な検索・フィルタリング
- S3サムネイル管理
- SNS統合お問い合わせフォーム
- レート制限機能
- メールサービスヘルスチェック
- バリデーション機能
- 個人情報保護機能


## 🌐 環境別サービス

### 開発環境サービス
| サービス | URL | 説明 |
|---------|-----|------|
| **API** | http://localhost:8000 | FastAPI アプリケーション |
| **API Docs** | http://localhost:8000/docs | Swagger UI |
| **Meilisearch** | http://localhost:7700 | 検索エンジン |
| **LocalStack** | http://localhost:4566 | AWS S3 エミュレーション |
| **MailHog** | http://localhost:8025 | メール送信テスト |
| **Redis** | localhost:6379 | レート制限・セッション管理 |

### 本番環境要件
- **AWS S3**: サムネイル・お問い合わせファイル保存
- **AWS SNS**: リアルタイム通知
- **AWS SES**: メール送信（推奨）
- **Redis**: レート制限・セッション管理
- **Meilisearch**: 検索エンジン
- **Gunicorn**: WSGIサーバー

## 🔧 本番環境設定

## 📚 API エンドポイント

### 記事管理
- `POST /api/v1/news` - 記事作成
- `GET /api/v1/news` - 記事一覧取得（フィルタリング・ページネーション対応）
- `GET /api/v1/news/{id}` - 個別記事取得
- `PUT /api/v1/news/{id}` - 記事更新
- `DELETE /api/v1/news/{id}` - 記事削除

### 検索・分析
- `GET /api/v1/news/search` - 記事検索（全文検索・フィルタリング対応）
- `GET /api/v1/news/facets` - ファセットカウント取得

### サムネイル管理（AWS S3統合）
- `POST /api/v1/news/thumbnails/s3` - S3サムネイル画像アップロード
- `GET /api/v1/news/thumbnails/s3/list` - S3サムネイル一覧取得
- `DELETE /api/v1/news/thumbnails/s3/{filename}` - S3サムネイル画像削除
- `GET /api/v1/news/s3/health` - S3サービスヘルスチェック

### お問い合わせ・メール機能（SNS統合）
- `POST /api/v1/contact` - **お問い合わせフォーム送信（推奨）**
  - ✅ S3への自動保存
  - ✅ SNS通知（本番環境）
  - ✅ レート制限（本番環境のみ: IP 5回/時間、メール 3回/時間）
- `POST /api/v1/contact/sync` - 同期版お問い合わせ（テスト用）
- `POST /api/v1/contact/legacy` - 従来版お問い合わせ（後方互換性）
- `GET /api/v1/email/health` - メールサービスヘルスチェック
- `POST /api/v1/email/test` - テストメール送信（開発用）

## 📁 プロジェクト構成
```
news_api/
├── app/
│   ├── main.py              # FastAPIアプリケーション
│   ├── schemas.py           # Pydanticスキーマ
│   ├── search.py            # Meilisearch操作
│   ├── email_service.py     # SNS統合メールサービス
│   ├── s3_service.py        # S3操作サービス
│   └── routers/
│       ├── news.py          # ニュース記事API
│       └── contact.py       # お問い合わせAPI
├── tests/
│   ├── test_api.py          # 包括的APIテスト
│   └── manual_email_test.py # 手動メールテスト
├── scripts/                 # 開発・運用スクリプト
├── logs/                    # ログファイル格納
│   └── .gitkeep            # ディレクトリ保持用
├── localstack-init/         # LocalStack初期化設定
├── localstack-data/         # LocalStack実行時データ
├── docker-compose.dev.yml   # 開発環境用Docker設定
├── docker-compose.prod.yml  # 本番環境用Docker設定
├── Pipfile                  # 依存関係管理
├── Pipfile.lock            # 依存関係ロック
├── pyproject.toml          # プロジェクト設定
├── .env                     # 環境変数（要作成）
├── env.example              # 環境変数テンプレート
├── .gitignore              # Git除外設定
├── LICENSE                 # ライセンス
└── README.md               # このファイル
```

## 💡 使用例

### 記事作成
```bash
curl -X POST "http://localhost:8000/api/v1/news" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "AI技術の最新動向",
    "content": "人工知能技術の発展について...",
    "category": "technology",
    "author": "山田太郎",
    "tags": ["AI", "機械学習", "Python"],
    "published": true,
    "thumbnail_url": "http://localhost:4566/news-api-thumbnails/thumbnails/sample.jpg",
    "thumbnail_alt": "AI技術のイメージ"
  }'
```

### お問い合わせフォーム送信（SNS統合版）

#### 最小限の例（必須項目のみ）
```bash
curl -X POST "http://localhost:8000/api/v1/contact" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "yamada@example.com",
    "subject": "APIについて",
    "message": "News APIの機能について教えてください。"
  }'
```

#### 全項目入力の例
```bash
curl -X POST "http://localhost:8000/api/v1/contact" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "山田太郎",
    "email": "yamada@example.com",
    "subject": "APIについて",
    "message": "News APIの機能について教えてください。",
    "phone": "090-1234-5678",
    "company": "株式会社サンプル"
  }'
```

### サムネイルアップロード（S3）
```bash
curl -X POST "http://localhost:8000/api/v1/news/thumbnails/s3" \
  -F "file=@thumbnail.jpg"
```

### 記事検索
```bash
# キーワード検索
curl "http://localhost:8000/api/v1/news/search?q=Python"

# フィルタリング検索
curl "http://localhost:8000/api/v1/news/search?category=technology&published=true"

# 複合検索
curl "http://localhost:8000/api/v1/news/search?q=AI&category=technology&tags=機械学習"
```

## 🔒 プライバシー保護機能

### 個人情報の自動マスク
リクエストログ出力時に個人情報を自動的に完全マスクします：

- **メールアドレス**: `user@example.com` → `*****************`
- **電話番号**: `090-1234-5678` → `*************`
- **氏名**: `山田太郎` → `****`
- **会社名**: `株式会社テスト` → `*******`

### 対象フィールド
- `email`: メールアドレス（フィールド名に`email`を含む場合も対象）
- `phone`: 電話番号
- `name`: 氏名
- `company`: 会社名

### マスク機能の特徴
- **完全マスク**: 全ての文字を`*`で置換（元の長さを保持）
- JSON形式と非JSON形式の両方に対応
- 個人情報以外のデータは変更なし
- 開発・本番環境の両方で動作
- セキュリティ重視の設計

## 📝 ライセンス

このプロジェクトはMITライセンスの下で公開されています。詳細は[LICENSE](LICENSE)ファイルを参照してください。
