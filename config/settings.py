#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
設定管理モジュール
"""

import os
import json
from pathlib import Path

# 設定ファイルのパス
CONFIG_DIR = Path(__file__).parent
USAGE_LOG_FILE = CONFIG_DIR / "usage_log.json"
USER_SETTINGS_FILE = CONFIG_DIR / "user_settings.json"

# デフォルト設定
DEFAULT_SETTINGS = {
    "whisper": {
        "model": "large",
        "language": "ja"
    },
    "claude": {
        "model": "claude-sonnet-4-20250514",
        "temperature": 0.5,
        "max_tokens": 8000
    },
    "article": {
        "min_characters": 4000,
        "default_style": "親しみやすい「です・ます」調",
        "reference_site": "",
        "custom_prompt": ""
    },
    "wordpress": {
        "site_url": "",
        "username": "",
        "password": "",
        "timeout": 30,
        "category": "ポッドキャスト",
        "status": "draft"
    },
    "limits": {
        "daily_limit": 5,
        "timezone": "Asia/Tokyo"
    }
}

def load_settings():
    """設定を読み込み"""
    try:
        settings = DEFAULT_SETTINGS.copy()
        
        # ユーザー設定ファイルがある場合はマージ
        if USER_SETTINGS_FILE.exists():
            with open(USER_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                user_settings = json.load(f)
            # ディープマージ
            for key, value in user_settings.items():
                if key in settings and isinstance(settings[key], dict) and isinstance(value, dict):
                    settings[key].update(value)
                else:
                    settings[key] = value
        
        # 環境変数からWordPress設定を読み込み
        env_file = Path(__file__).parent.parent / ".env"
        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('WORDPRESS_URL='):
                        settings['wordpress']['site_url'] = line.split('=', 1)[1].strip()
                    elif line.startswith('WORDPRESS_USERNAME='):
                        settings['wordpress']['username'] = line.split('=', 1)[1].strip()
                    elif line.startswith('WORDPRESS_PASSWORD='):
                        settings['wordpress']['password'] = line.split('=', 1)[1].strip()
        
        return settings
    except Exception:
        return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    """設定を保存"""
    try:
        with open(USER_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def get_api_key():
    """Claude API キーを取得"""
    # .envファイルから読み込み
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                if line.startswith('ANTHROPIC_API_KEY='):
                    return line.split('=', 1)[1].strip()
    
    # 環境変数から取得
    return os.getenv("ANTHROPIC_API_KEY")

def get_secret_key():
    """Flask Secret Keyを取得"""
    return os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")