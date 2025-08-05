#!/usr/bin/env python3
"""
ポッドキャスト音声処理モジュール
"""

import os
import logging
import tempfile
import whisper
import requests
import yt_dlp
from pathlib import Path

logger = logging.getLogger(__name__)

class PodcastProcessor:
    def __init__(self):
        self.whisper_model = None
    
    def download_audio(self, url: str) -> str:
        """音声ファイルのダウンロード"""
        logger.info(f"音声をダウンロード中: {url}")
        
        try:
            # 直接ファイルダウンロードを試行
            if self._is_direct_file_url(url):
                return self._download_direct_file(url)
            else:
                # yt-dlpでダウンロード
                return self._download_with_ytdlp(url)
        except Exception as e:
            logger.error(f"音声ダウンロードエラー: {e}")
            raise
    
    def _is_direct_file_url(self, url: str) -> bool:
        """直接ファイルURLかどうかを判定"""
        audio_extensions = ['.mp3', '.wav', '.m4a', '.mp4', '.flac', '.ogg']
        return any(url.lower().endswith(ext) for ext in audio_extensions)
    
    def _download_direct_file(self, url: str) -> str:
        """直接ファイルをダウンロード"""
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # 一時ファイルに保存
            temp_dir = tempfile.gettempdir()
            filename = f"podcast_{os.urandom(4).hex()}.m4a"
            file_path = os.path.join(temp_dir, filename)
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"直接ダウンロード完了: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"直接ダウンロードエラー: {e}")
            raise
    
    def _download_with_ytdlp(self, url: str) -> str:
        """yt-dlpでダウンロード"""
        temp_dir = tempfile.gettempdir()
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'{temp_dir}/%(title)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get('title', 'unknown')
                
                # 実際のファイル名を探す
                for file in os.listdir(temp_dir):
                    if title.replace('/', '_') in file and file.endswith('.wav'):
                        filename = os.path.join(temp_dir, file)
                        logger.info(f"yt-dlpダウンロード完了: {filename}")
                        return filename
                
                raise Exception("ダウンロードしたファイルが見つかりません")
        except Exception as e:
            logger.error(f"yt-dlpダウンロードエラー: {e}")
            raise
    
    def transcribe_audio(self, audio_path: str, whisper_settings: dict = None) -> str:
        """音声の文字起こし"""
        logger.info(f"文字起こし開始: {audio_path}")
        
        try:
            # Whisperモデルを読み込み
            if self.whisper_model is None:
                model_name = whisper_settings.get("model", "large") if whisper_settings else "large"
                logger.info(f"Whisperモデルを読み込み中: {model_name}")
                self.whisper_model = whisper.load_model(model_name)
            
            # 文字起こし実行
            language = whisper_settings.get("language", "ja") if whisper_settings else "ja"
            result = self.whisper_model.transcribe(audio_path, language=language)
            
            transcript = result["text"]
            logger.info(f"文字起こし完了: {len(transcript)}文字")
            
            return transcript
        except Exception as e:
            logger.error(f"文字起こしエラー: {e}")
            raise