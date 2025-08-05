#!/usr/bin/env python3
"""
WordPress投稿機能の単体テスト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import logging
from config.settings import load_settings
from core.wordpress_poster import WordPressPoster

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_settings_loading():
    """設定読み込みテスト"""
    print("=== 設定読み込みテスト ===")
    try:
        settings = load_settings()
        wp_settings = settings.get('wordpress', {})
        
        print(f"WordPress設定:")
        print(f"  site_url: {wp_settings.get('site_url', 'None')}")
        print(f"  username: {wp_settings.get('username', 'None')}")
        print(f"  password: {'***' if wp_settings.get('password') else 'None'}")
        print(f"  status: {wp_settings.get('status', 'None')}")
        print(f"  timeout: {wp_settings.get('timeout', 'None')}")
        
        # 検証チェック
        has_all = bool(wp_settings.get('site_url') and wp_settings.get('username') and wp_settings.get('password'))
        print(f"設定完全性: {has_all}")
        
        return wp_settings
        
    except Exception as e:
        print(f"設定読み込みエラー: {e}")
        import traceback
        print(f"トレースバック: {traceback.format_exc()}")
        return None

def test_wordpress_poster_init(wp_settings):
    """WordPressPoster初期化テスト"""
    print("\n=== WordPressPoster初期化テスト ===")
    try:
        poster = WordPressPoster(wp_settings)
        print(f"初期化成功:")
        print(f"  site_url: {poster.site_url}")
        print(f"  username: {poster.username}")
        print(f"  status: {poster.status}")
        print(f"  timeout: {poster.timeout}")
        
        # 投稿データの確認
        test_data = {'title': 'test', 'content': 'test', 'summary': 'test'}
        print(f"  実際の投稿ステータス: {'publish' if poster.status == 'publish' else 'draft'}")
        
        # 設定検証
        is_valid = poster._validate_settings()
        print(f"設定検証結果: {is_valid}")
        
        return poster
        
    except Exception as e:
        print(f"初期化エラー: {e}")
        import traceback
        print(f"トレースバック: {traceback.format_exc()}")
        return None

def test_login(poster):
    """ログインテスト"""
    print("\n=== ログインテスト ===")
    try:
        success = poster._login()
        print(f"ログイン結果: {success}")
        return success
        
    except Exception as e:
        print(f"ログインエラー: {e}")
        import traceback
        print(f"トレースバック: {traceback.format_exc()}")
        return False

def test_post_article(poster):
    """記事投稿テスト"""
    print("\n=== 記事投稿テスト ===")
    
    # テスト用記事データ
    test_article = {
        'title': '【テスト投稿】WordPress自動投稿テスト',
        'content': '''<h2>WordPress自動投稿テスト</h2>
<p>これはWordPress自動投稿システムのテストです。</p>
<p>ブラウザ自動化によるwp-admin経由での投稿テストを実行しています。</p>
<ul>
<li>自動ログイン機能</li>
<li>投稿フォーム自動操作</li>
<li>記事公開機能</li>
</ul>
<p>※この記事はポッドキャスト音声データを元にAIが書き起こし、編集したものです。</p>''',
        'summary': 'WordPress自動投稿システムのテスト投稿です。ブラウザ自動化による投稿機能を検証しています。',
        'tags': ['テスト', 'WordPress', '自動投稿']
    }
    
    try:
        success = poster.post_article(test_article)
        print(f"投稿結果: {success}")
        return success
        
    except Exception as e:
        print(f"投稿エラー: {e}")
        import traceback
        print(f"トレースバック: {traceback.format_exc()}")
        return False

def main():
    """メインテスト関数"""
    print("WordPress投稿機能単体テスト開始\n")
    
    # 1. 設定読み込みテスト
    wp_settings = test_settings_loading()
    if not wp_settings:
        print("設定読み込みに失敗しました")
        return
    
    # 2. WordPressPoster初期化テスト
    poster = test_wordpress_poster_init(wp_settings)
    if not poster:
        print("WordPressPoster初期化に失敗しました")
        return
    
    # 3. ログインテスト
    login_success = test_login(poster)
    if not login_success:
        print("ログインに失敗しました")
        return
    
    # 4. 記事投稿テスト
    post_success = test_post_article(poster)
    if post_success:
        print("\n✅ すべてのテストが成功しました！")
    else:
        print("\n❌ 記事投稿に失敗しました")

if __name__ == "__main__":
    main()