import requests
import json
from datetime import datetime, timezone, timedelta
import random
from PIL import Image, ImageDraw, ImageFont
import io
import os

# サンプルデータ
categories = ["technology", "business", "science", "health", "entertainment"]
tags = ["AI", "Python", "機械学習", "データ分析", "クラウド", "セキュリティ", "ビジネス", "経済", "医療", "健康", "映画", "音楽", "ゲーム"]
authors = ["山田太郎", "佐藤花子", "鈴木一郎", "田中美咲", "伊藤健太"]

# サムネイル用の色とテーマ
thumbnail_themes = {
    "technology": {"colors": ["#007ACC", "#4CAF50", "#FF9800"], "icons": ["💻", "🔧", "⚡"]},
    "business": {"colors": ["#2196F3", "#FF5722", "#9C27B0"], "icons": ["📊", "💼", "📈"]},
    "science": {"colors": ["#4CAF50", "#00BCD4", "#8BC34A"], "icons": ["🔬", "🧪", "🌟"]},
    "health": {"colors": ["#E91E63", "#FF5722", "#FFC107"], "icons": ["❤️", "🏥", "💊"]},
    "entertainment": {"colors": ["#9C27B0", "#E91E63", "#FF9800"], "icons": ["🎬", "🎵", "🎮"]}
}

def hex_to_rgb(hex_color):
    """16進数カラーコードをRGBタプルに変換"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def create_thumbnail_image(category: str, title: str, index: int) -> bytes:
    """カテゴリに応じたサムネイル画像を生成"""
    # 画像サイズ
    width, height = 400, 300
    
    # カテゴリのテーマを取得
    theme = thumbnail_themes.get(category, thumbnail_themes["technology"])
    bg_color = hex_to_rgb(random.choice(theme["colors"]))
    icon = random.choice(theme["icons"])
    
    # 画像を作成
    image = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(image)
    
    # グラデーション効果を追加
    for y in range(height):
        alpha = y / height
        gradient_color = tuple(int(c * (1 - alpha * 0.3)) for c in bg_color)
        draw.line([(0, y), (width, y)], fill=gradient_color)
    
    try:
        # フォントを設定（システムフォントを試行）
        try:
            # macOSの場合
            font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
            font_medium = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
            font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
        except:
            try:
                # Linuxの場合
                font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
                font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
                font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
            except:
                # デフォルトフォント
                font_large = ImageFont.load_default()
                font_medium = ImageFont.load_default()
                font_small = ImageFont.load_default()
    except:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # アイコンを描画
    icon_size = 60
    icon_x = width // 2
    icon_y = height // 2 - 40
    draw.text((icon_x, icon_y), icon, font=font_large, fill='white', anchor='mm')
    
    # タイトルを描画（短縮版）
    short_title = f"記事 {index}"
    title_y = icon_y + 50
    draw.text((width // 2, title_y), short_title, font=font_medium, fill='white', anchor='mm')
    
    # カテゴリを描画
    category_text = category.upper()
    category_y = title_y + 30
    draw.text((width // 2, category_y), category_text, font=font_small, fill='white', anchor='mm')
    
    # 画像をバイト配列に変換
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return img_byte_arr.getvalue()

def upload_thumbnail_to_s3(image_data: bytes, filename: str) -> str:
    """S3にサムネイル画像をアップロード"""
    base_url = "http://localhost:8000/api/v1/news/thumbnails/s3"
    
    files = {
        'file': (filename, io.BytesIO(image_data), 'image/png')
    }
    
    try:
        response = requests.post(base_url, files=files)
        response.raise_for_status()
        data = response.json()
        return data['s3_url']
    except requests.exceptions.RequestException as e:
        print(f"サムネイルアップロードに失敗しました: {str(e)}")
        return None

def generate_sample_article_with_thumbnail(index: int) -> dict:
    """サムネイル付きサンプル記事を生成"""
    # ランダムな日時を生成（過去30日以内）
    days_ago = random.randint(0, 30)
    created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    
    category = random.choice(categories)
    
    # 記事の基本情報
    article = {
        "title": f"サンプル記事 {index}: {random.choice(['最新', '注目', '特集'])}の{random.choice(['技術', 'ビジネス', '科学', '健康', 'エンタメ'])}ニュース",
        "content": f"""
これはサンプル記事{index}の本文です。

## 概要
この記事では、{random.choice(['最新の技術動向', 'ビジネス戦略', '科学の発見', '健康管理', 'エンターテイメント'])}について詳しく解説します。

## 詳細
{random.choice([
    '人工知能（AI）技術の進化により、私たちの生活は大きく変化しています。',
    'グローバル経済の変動により、ビジネス環境は日々変化しています。',
    '最新の科学研究により、新たな発見が相次いでいます。',
    '健康管理の重要性がますます高まっています。',
    'エンターテイメント業界は、デジタル化の波に乗って進化を続けています。'
])}

機械学習やデータ分析の技術を活用することで、より効率的な解決策を見つけることができます。
特に、Pythonを使った開発では、豊富なライブラリを活用できるため、迅速なプロトタイピングが可能です。

## 結論
今後も{random.choice(['技術革新', '経済発展', '科学の進歩', '健康増進', 'エンターテイメント'])}に注目していきましょう。
        """.strip(),
        "category": category,
        "author": random.choice(authors),
        "tags": random.sample(tags, random.randint(1, 3)),
        "published": random.choice([True, False])
    }
    
    # サムネイル画像を生成
    print(f"記事 {index} のサムネイル画像を生成中...")
    try:
        image_data = create_thumbnail_image(category, article["title"], index)
        filename = f"sample-article-{index}-{category}.png"
        
        # S3にアップロード
        thumbnail_url = upload_thumbnail_to_s3(image_data, filename)
        if thumbnail_url:
            article["thumbnail_url"] = thumbnail_url
            article["thumbnail_alt"] = f"サンプル記事 {index} のサムネイル画像"
            print(f"✓ サムネイルをアップロードしました: {thumbnail_url}")
        else:
            print(f"✗ サムネイルアップロードに失敗しました")
    except Exception as e:
        print(f"✗ サムネイル生成に失敗しました: {str(e)}")
    
    return article

def create_sample_articles_with_thumbnails(num_articles: int = 10):
    """サムネイル付きサンプル記事を作成"""
    base_url = "http://localhost:8000/api/v1/news"
    
    print(f"{num_articles}件のサムネイル付きサンプル記事を作成します...")
    print("Pillowライブラリが必要です。インストールされていない場合は 'pipenv install pillow' を実行してください。")
    
    created_count = 0
    for i in range(1, num_articles + 1):
        article = generate_sample_article_with_thumbnail(i)
        try:
            response = requests.post(base_url, json=article)
            response.raise_for_status()
            created_count += 1
            thumbnail_status = "✓ サムネイル付き" if article.get("thumbnail_url") else "✗ サムネイルなし"
            print(f"✓ 記事 {i} を作成しました: {article['title']} ({thumbnail_status})")
        except requests.exceptions.RequestException as e:
            print(f"✗ 記事 {i} の作成に失敗しました: {str(e)}")
    
    print(f"\n作成完了！ {created_count}/{num_articles} 件の記事を作成しました。")
    print("記事一覧を確認するには: http://localhost:8000/api/v1/news")
    print("検索機能を試すには: http://localhost:8000/api/v1/news/search")
    print("API仕様書を確認するには: http://localhost:8000/docs")
    print("S3サムネイル一覧: http://localhost:8000/api/v1/news/thumbnails/s3/list")

if __name__ == "__main__":
    # 15件のサムネイル付きサンプル記事を作成
    create_sample_articles_with_thumbnails(15) 