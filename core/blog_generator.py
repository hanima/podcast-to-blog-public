#!/usr/bin/env python3
"""
ブログ記事生成モジュール
"""

import json
import logging
import requests
import time
import random
import re
from anthropic import Anthropic
from bs4 import BeautifulSoup
from config.settings import get_api_key

logger = logging.getLogger(__name__)

class BlogGenerator:
    def __init__(self, user_settings: dict):
        self.claude_client = Anthropic(api_key=get_api_key())
        self.user_settings = user_settings
    
    def generate_article(self, transcript: str, episode_url: str = "") -> dict:
        """文字起こし結果をブログ記事に変換"""
        logger.info("ブログ記事への変換開始")
        
        # 参考サイトの文体を取得
        reference_style = self._get_reference_style()
        
        # プロンプトを構築
        prompt = self._build_prompt(transcript, reference_style, episode_url)
        
        try:
            # Claude APIで生成
            article_data = self._generate_with_claude(prompt)
            
            # 文字数チェックと詳細化
            article_data = self._ensure_minimum_length(article_data)
            
            logger.info(f"ブログ記事変換完了: {article_data['title']}")
            return article_data
        except Exception as e:
            logger.error(f"ブログ記事変換エラー: {e}")
            raise
    
    def _get_reference_style(self) -> str:
        """参考サイトの文体を取得"""
        article_settings = self.user_settings.get("article", {})
        reference_url = article_settings.get("reference_url", "")
        
        if not reference_url:
            return ""
        
        try:
            response = requests.get(reference_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 記事本文を抽出
            articles = soup.find_all(['article', 'div'], class_=lambda x: x and ('post' in x or 'content' in x))
            
            if articles:
                article_text = articles[0].get_text(strip=True)[:2000]
                return article_text
            
            return ""
        except Exception as e:
            logger.warning(f"参考サイトの取得に失敗: {e}")
            return ""
    
    def _build_prompt(self, transcript: str, reference_style: str, episode_url: str = "") -> str:
        """プロンプトを構築"""
        article_settings = self.user_settings.get("article", {})
        custom_style = article_settings.get("custom_style", "")
        min_characters = article_settings.get("min_characters", 4000)
        
        # 文体指定を構築
        style_instruction = ""
        if reference_style:
            style_instruction += f"""
参考として、以下の文体サンプルです：
{reference_style}

この文体を参考に、同じようなトーンとスタイルで記事を書いてください。
"""
        
        if custom_style:
            style_instruction += f"""
【カスタム文体要件】
{custom_style}
"""
        
        # Spotify埋め込みの指示を動的に追加
        spotify_instruction = ""
        if episode_url:
            episode_id = episode_url.split('/')[-1] if '/' in episode_url else episode_url
            spotify_instruction = f"""
12. 【重要】記事の末尾（注釈の前）に以下のSpotify埋め込みコードを必ず追加してください：
<iframe style="border-radius:12px" src="https://open.spotify.com/embed/episode/{episode_id}" width="100%" height="352" frameBorder="0" allowfullscreen="" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe>
"""

        prompt = f"""
以下のポッドキャストの文字起こし結果を、読みやすいブログ記事に変換してください。

【要件】
1. 適切な見出し（H2、H3）で構造化
2. 読みやすい段落分け
3. 重要なポイントは太字で強調
4. 必要に応じて箇条書きを使用
5. 自然な日本語で読みやすく
6. SEOを意識したタイトルを生成
7. 【重要】記事本文は必ず{min_characters}文字以上の日本語で書いてください
8. 記事タイトルは必ず内容に沿った具体的で魅力的なものにしてください
9. 文章は読み物風で、人間による語りかけるような親しみやすいトーンで書いてください
10. 【超重要】文字起こし内容から逸脱しないでください：
    - 記載されていない情報は絶対に追加しないでください
    - 推測や想像での補完は禁止です
    - 文字起こしにない具体的な数値、日付、人名、会社名は使用禁止
    - 「〜と思われます」「〜の可能性があります」など推測表現も避けてください
11. 記事の末尾に「※この記事はポッドキャスト音声データを元にAIが書き起こし、編集したものです。」を追加してください{spotify_instruction}

{style_instruction}

【文字起こし結果】
{transcript}

【出力形式】
以下のJSON形式で出力してください。HTMLは正しい形式で記述してください：
{{
  "title": "内容に沿った具体的な記事タイトル",
  "content": "<h2>見出し</h2><p>段落内容</p><h3>小見出し</h3><p>段落内容</p>",
  "summary": "記事の要約（200文字程度）",
  "tags": ["タグ1", "タグ2", "タグ3"]
}}

重要: 
- contentフィールドは必ず正しいHTMLタグで構造化し、JSONとして正しく出力してください
- contentフィールドの日本語文字数は必ず{min_characters}文字以上にしてください（HTMLタグは文字数に含めません）
- 文字数が足りない場合は絶対に追加執筆してください
"""
        
        return prompt
    
    def _generate_with_claude(self, prompt: str) -> dict:
        """Claude APIで記事生成"""
        claude_settings = self.user_settings.get("claude", {})
        temperature = claude_settings.get("temperature", 0.5)
        max_tokens = claude_settings.get("max_tokens", 8000)
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                content = ""
                with self.claude_client.messages.stream(
                    model="claude-sonnet-4-20250514",
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                ) as stream:
                    for text in stream.text_stream:
                        content += text
                
                # JSON解析
                article_data = json.loads(content, strict=False)
                return article_data
                
            except json.JSONDecodeError:
                # JSONコードブロック形式の場合
                try:
                    json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(1).strip()
                        article_data = json.loads(json_str, strict=False)
                        return article_data
                    
                    # 通常のJSONパターンを探す
                    json_match = re.search(r'\{(?:[^{}]|{[^{}]*})*\}', content, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(0)
                        article_data = json.loads(json_str, strict=False)
                        return article_data
                    
                    raise json.JSONDecodeError("JSON pattern not found", content, 0)
                except (json.JSONDecodeError, AttributeError) as e:
                    logger.error(f"JSON解析エラー: {e}")
                    logger.error(f"受信内容: {content[:500]}")
                    raise Exception("Claude APIからの適切なJSON応答を取得できませんでした")
            
            except Exception as e:
                if "overloaded" in str(e).lower() and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"Claude API過負荷、{wait_time:.1f}秒後にリトライ（{attempt + 1}/{max_retries}）")
                    time.sleep(wait_time)
                    continue
                else:
                    raise
    
    def _ensure_minimum_length(self, article_data: dict) -> dict:
        """最小文字数を確保"""
        article_settings = self.user_settings.get("article", {})
        min_characters = article_settings.get("min_characters", 4000)
        
        # HTMLタグを除いた文字数をチェック
        content_text = re.sub(r'<[^>]+>', '', article_data.get('content', ''))
        char_count = len(content_text)
        logger.info(f"1回目生成完了: {char_count}文字")
        
        if char_count < min_characters:
            logger.info("文字数不足のため詳細化を実行中...")
            return self._expand_article(article_data, min_characters, episode_url)
        
        return article_data
    
    def _expand_article(self, article_data: dict, min_characters: int, episode_url: str = "") -> dict:
        """記事を詳細化"""
        # Spotify埋め込みの指示を動的に追加
        spotify_instruction = ""
        if episode_url:
            episode_id = episode_url.split('/')[-1] if '/' in episode_url else episode_url
            spotify_instruction = f"""
7. 【重要】記事の末尾（注釈の前）に以下のSpotify埋め込みコードを必ず追加してください：
<iframe style="border-radius:12px" src="https://open.spotify.com/embed/episode/{episode_id}" width="100%" height="352" frameBorder="0" allowfullscreen="" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe>
"""

        expand_prompt = f"""
以下の記事内容を基に、各セクションをより詳細に展開し、{min_characters}文字以上の完全な記事にしてください。

【現在の記事】
{article_data.get('content', '')}

【拡張要求】
1. 文字起こし内容の範囲内で各見出しをより詳細に説明
2. 既存の情報をより丁寧に解説
3. 文字起こしで言及された内容の背景を詳しく説明
4. 新しい情報は一切追加せず、既存情報の深掘りのみ
5. 必ず{min_characters}文字以上にしてください
6. 記事の末尾に「※この記事はポッドキャスト音声データを元にAIが書き起こし、編集したものです。」を追加{spotify_instruction}

以下のJSON形式で出力してください：
{{
  "title": "{article_data.get('title', '')}",
  "content": "詳細化されたHTML形式の記事本文（{min_characters}文字以上）",
  "summary": "記事の要約（200文字程度）",
  "tags": {article_data.get('tags', [])}
}}
"""
        
        try:
            expanded_data = self._generate_with_claude(expand_prompt)
            expanded_text = re.sub(r'<[^>]+>', '', expanded_data.get('content', ''))
            expanded_char_count = len(expanded_text)
            logger.info(f"2回目生成完了: {expanded_char_count}文字")
            return expanded_data
        except Exception as e:
            logger.warning(f"詳細化に失敗、1回目の記事を使用: {e}")
            return article_data