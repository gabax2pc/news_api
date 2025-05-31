import requests
import json
from datetime import datetime, timezone, timedelta
import random

# サンプルデータ
categories = ["technology", "business", "science", "health", "entertainment"]
tags = ["AI", "Python", "機械学習", "データ分析", "クラウド", "セキュリティ", "ビジネス", "経済", "医療", "健康", "映画", "音楽", "ゲーム"]
authors = ["山田太郎", "佐藤花子", "鈴木一郎", "田中美咲", "伊藤健太"]

def generate_sample_article(index: int) -> dict:
    """サンプル記事を生成します"""
    # ランダムな日時を生成（過去30日以内）
    days_ago = random.randint(0, 30)
    created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    
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
        "category": random.choice(categories),
        "author": random.choice(authors),
        "tags": random.sample(tags, random.randint(1, 3)),
        "published": random.choice([True, False])
    }
    
    return article

def create_sample_articles(num_articles: int = 10):
    """指定された数のサンプル記事を作成します"""
    base_url = "http://localhost:8000/api/v1/news"
    
    print(f"{num_articles}件のサンプル記事を作成します...")
    
    created_count = 0
    for i in range(1, num_articles + 1):
        article = generate_sample_article(i)
        try:
            response = requests.post(base_url, json=article)
            response.raise_for_status()
            created_count += 1
            print(f"✓ 記事 {i} を作成しました: {article['title']}")
        except requests.exceptions.RequestException as e:
            print(f"✗ 記事 {i} の作成に失敗しました: {str(e)}")
    
    print(f"\n作成完了！ {created_count}/{num_articles} 件の記事を作成しました。")
    print("記事一覧を確認するには: http://localhost:8000/api/v1/news")
    print("検索機能を試すには: http://localhost:8000/api/v1/news/search")
    print("API仕様書を確認するには: http://localhost:8000/docs")

if __name__ == "__main__":
    # 20件のサンプル記事を作成
    create_sample_articles(20) 