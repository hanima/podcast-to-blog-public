#!/usr/bin/env python3
"""
WordPress投稿モジュール
"""

import logging
import requests
import time
import re
from bs4 import BeautifulSoup
from typing import Dict

logger = logging.getLogger(__name__)

class WordPressPoster:
    def __init__(self, wordpress_settings: dict):
        self.settings = wordpress_settings
        site_url = wordpress_settings.get("site_url", "").rstrip('/')
        # /wp-admin が含まれている場合は除去
        if site_url.endswith('/wp-admin'):
            site_url = site_url.replace('/wp-admin', '')
        self.site_url = site_url
        self.username = wordpress_settings.get("username", "")
        self.password = wordpress_settings.get("password", "")
        self.category = wordpress_settings.get("category", "ポッドキャスト")
        self.status = wordpress_settings.get("status", "draft")
        self.timeout = wordpress_settings.get("timeout", 30)
        
        # セッションは初期化時ではなく、使用時に作成（threading対応）
        self.session = None
    
    def post_article(self, article_data: dict) -> bool:
        """WordPressに記事を投稿"""
        if not self._validate_settings():
            logger.warning("WordPress設定が不完全です")
            return False
        
        logger.info("WordPress投稿開始（ブラウザ自動化モード）")
        
        # ブラウザ自動化で直接投稿
        return self._post_via_browser_automation(article_data)
    
    def _validate_settings(self) -> bool:
        """設定を検証"""
        return bool(self.site_url and self.username and self.password)
    
    def _post_via_browser_automation(self, article_data: dict) -> bool:
        """ブラウザ自動化で投稿（wp-admin経由）"""
        try:
            logger.info("WordPressブラウザ自動投稿開始")
            
            # セッションを新規作成（threading対応）
            self.session = requests.Session()
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            
            # ログイン
            if not self._login():
                return False
            
            # 少し待機
            time.sleep(1)
            
            # 投稿
            return self._post_article(article_data)
            
        except Exception as e:
            logger.error(f"ブラウザ自動化エラー: {e}")
            return False
    
    def _login(self) -> bool:
        """WordPressダッシュボードにログイン"""
        try:
            # 1. ログインページを取得
            login_url = f"{self.site_url}/wp-login.php"
            logger.info(f"ログインページにアクセス: {login_url}")
            
            response = self.session.get(login_url, timeout=self.timeout)
            response.raise_for_status()
            
            # 2. ログインフォームを解析
            soup = BeautifulSoup(response.content, 'html.parser')
            login_form = soup.find('form', {'id': 'loginform'})
            
            if not login_form:
                logger.error("ログインフォームが見つかりません")
                return False
            
            # 3. 隠しフィールドを取得
            hidden_fields = {}
            for input_tag in login_form.find_all('input', {'type': 'hidden'}):
                if input_tag.get('name') and input_tag.get('value'):
                    hidden_fields[input_tag.get('name')] = input_tag.get('value')
            
            # 4. ログインデータを準備
            login_data = {
                'log': self.username,
                'pwd': self.password,
                'wp-submit': 'ログイン',
                'redirect_to': f"{self.site_url}/wp-admin/",
                'testcookie': '1'
            }
            login_data.update(hidden_fields)
            
            # 5. ログインを実行
            logger.info("ログイン実行中...")
            response = self.session.post(login_url, data=login_data, timeout=self.timeout)
            response.raise_for_status()
            
            # 6. ログイン成功を確認
            if 'wp-admin' in response.url and 'login' not in response.url:
                logger.info("ログイン成功")
                return True
            else:
                logger.error("ログイン失敗")
                logger.debug(f"リダイレクト先URL: {response.url}")
                return False
                
        except Exception as e:
            logger.error(f"ログインエラー詳細: {type(e).__name__}: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"レスポンス詳細: {e.response.status_code} {e.response.text[:200]}")
            return False
    
    def _post_article(self, article_data: Dict[str, str]) -> bool:
        """記事を投稿"""
        try:
            # 1. 新規投稿ページを取得
            new_post_url = f"{self.site_url}/wp-admin/post-new.php"
            logger.info(f"新規投稿ページにアクセス: {new_post_url}")
            
            response = self.session.get(new_post_url, timeout=self.timeout)
            response.raise_for_status()
            
            # 2. 投稿フォームを解析
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 投稿フォームから隠しフィールドを取得
            hidden_fields = {}
            
            # 最初のフォーム（投稿フォーム）から隠しフィールドを抽出
            forms = soup.find_all('form')
            if forms:
                # 最初のフォームが投稿フォーム
                main_form = forms[0]
                hidden_inputs = main_form.find_all('input', {'type': 'hidden'})
                for inp in hidden_inputs:
                    name = inp.get('name')
                    value = inp.get('value')
                    if name and value:
                        hidden_fields[name] = value
            
            # 必須フィールドを確認
            required_fields = ['_wpnonce', 'user_ID', 'post_ID']
            for field in required_fields:
                if field not in hidden_fields:
                    logger.error(f"必須フィールド '{field}' が見つかりません")
                    return False
            
            # actionフィールドを正しく設定
            hidden_fields['action'] = 'editpost'
            hidden_fields['originalaction'] = 'editpost'
            
            logger.info(f"取得したフィールド: {list(hidden_fields.keys())}")
            
            # 3. 投稿データを準備
            post_data = {
                'post_title': article_data['title'],
                'content': article_data['content'],
                'excerpt': article_data.get('summary', ''),
                'post_status': 'publish' if self.status == 'publish' else 'draft',
                'publish': '公開' if self.status == 'publish' else '下書きとして保存',
                'save': '公開' if self.status == 'publish' else '下書きとして保存'
            }
            
            # 重要な隠しフィールドのみを追加
            important_fields = ['_wpnonce', '_wp_http_referer', 'user_ID', 'post_ID', 'post_type', 'action', 'originalaction']
            for field in important_fields:
                if field in hidden_fields:
                    post_data[field] = hidden_fields[field]
            
            logger.info(f"投稿データ準備完了: {article_data['title'][:50]}...")
            
            # 4. 投稿を実行
            logger.info("投稿実行中...")
            response = self.session.post(f"{self.site_url}/wp-admin/post.php", data=post_data, timeout=self.timeout)
            response.raise_for_status()
            
            logger.info(f"投稿後のURL: {response.url}")
            
            # 5. 投稿成功を確認
            if 'post.php' in response.url and ('message=6' in response.url or 'message=1' in response.url):
                logger.info("投稿成功")
                return True
            elif 'edit.php' in response.url:
                logger.info("投稿成功（投稿一覧にリダイレクト）")
                return True
            else:
                # エラーメッセージを確認
                soup = BeautifulSoup(response.content, 'html.parser')
                error_divs = soup.find_all('div', class_='error')
                if error_divs:
                    logger.error(f"投稿エラー: {error_divs[0].get_text()}")
                else:
                    logger.error("投稿失敗")
                    logger.debug(f"Response URL: {response.url}")
                return False
                
        except Exception as e:
            logger.error(f"投稿エラー: {e}")
            return False