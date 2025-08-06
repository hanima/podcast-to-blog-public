#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Podcast to Blog - Web版
汎用ポッドキャスト→ブログ自動化ツール
"""

from flask import Flask, render_template, request, jsonify
import logging
import os
import datetime
from config.settings import get_api_key, get_secret_key, load_settings
from config.usage_limiter import UsageLimiter

app = Flask(__name__)
app.secret_key = get_secret_key()

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 利用制限管理
usage_limiter = UsageLimiter(daily_limit=5)

@app.route('/')
def index():
    """メインページ"""
    # 利用状況を取得
    client_ip = request.remote_addr
    usage_info = usage_limiter.get_usage_info(client_ip)
    
    return render_template('index.html', usage_info=usage_info)

@app.route('/api/usage-info')
def api_usage_info():
    """利用状況取得API"""
    client_ip = request.remote_addr
    usage_info = usage_limiter.get_usage_info(client_ip)
    return jsonify(usage_info)

@app.route('/api/process', methods=['POST'])
def api_process():
    """処理開始API"""
    try:
        # 利用制限チェック
        client_ip = request.remote_addr
        usage_info = usage_limiter.get_usage_info(client_ip)
        
        if not usage_info["can_use"]:
            return jsonify({
                'error': f'本日の利用上限（{usage_info["daily_limit"]}回）に達しました。{usage_info["next_reset"]}にリセットされます。'
            }), 429
        
        data = request.get_json()
        file_url = data.get('file_url', '').strip()
        episode_url = data.get('episode_url', '').strip()
        
        if not file_url:
            return jsonify({'error': 'ファイルURLを入力してください'}), 400
        
        if not file_url.startswith('http'):
            return jsonify({'error': '有効なURLを入力してください'}), 400
        
        # 利用回数を消費
        success, message = usage_limiter.use_quota(client_ip)
        if not success:
            return jsonify({'error': message}), 429
        
        # ユーザー設定を取得
        user_settings = data.get('settings', {})
        
        # 実際の処理を開始（バックグラウンド処理）
        import threading
        import uuid
        
        task_id = str(uuid.uuid4())
        
        # 処理状況を保存するためのグローバル辞書
        if not hasattr(app, 'processing_status'):
            app.processing_status = {}
        
        app.processing_status[task_id] = {
            'current_step': 1,
            'total_steps': 4,
            'step_name': '処理開始',
            'status': '処理を開始しました',
            'error': None,
            'timestamp': None,
            'logs': []
        }
        
        # バックグラウンドで処理を実行
        thread = threading.Thread(
            target=process_podcast_background,
            args=(task_id, file_url, episode_url, user_settings)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'task_id': task_id,
            'message': '処理を開始しました'
        })
        
    except Exception as e:
        logger.error(f"API処理エラー: {e}")
        return jsonify({'error': 'サーバーエラーが発生しました'}), 500

@app.route('/api/status/<task_id>')
def api_status(task_id):
    """進行状況取得API"""
    try:
        if not hasattr(app, 'processing_status'):
            app.processing_status = {}
        
        status = app.processing_status.get(task_id)
        if not status:
            return jsonify({'error': 'タスクが見つかりません'}), 404
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"ステータス取得エラー: {e}")
        return jsonify({'error': 'サーバーエラーが発生しました'}), 500

@app.route('/api/result/<task_id>')
def api_result(task_id):
    """処理結果取得API"""
    try:
        if not hasattr(app, 'processing_status'):
            return jsonify({'error': 'タスクが見つかりません'}), 404
        
        status = app.processing_status.get(task_id)
        if not status:
            return jsonify({'error': 'タスクが見つかりません'}), 404
        
        result = status.get('result')
        if not result:
            return jsonify({'error': '処理がまだ完了していません'}), 404
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"結果取得エラー: {e}")
        return jsonify({'error': 'サーバーエラーが発生しました'}), 500

@app.route('/api/debug/tasks')
def api_debug_tasks():
    """デバッグ用：全タスク一覧"""
    try:
        if not hasattr(app, 'processing_status'):
            return jsonify({'tasks': []})
        
        tasks = []
        for task_id, status in app.processing_status.items():
            tasks.append({
                'task_id': task_id,
                'step': f"{status.get('current_step', 0)}/{status.get('total_steps', 4)}",
                'step_name': status.get('step_name', 'unknown'),
                'status': status.get('status', 'unknown'),
                'error': status.get('error'),
                'has_result': 'result' in status,
                'timestamp': status.get('timestamp')
            })
        
        return jsonify({'tasks': tasks})
        
    except Exception as e:
        logger.error(f"デバッグタスク一覧エラー: {e}")
        return jsonify({'error': 'サーバーエラーが発生しました'}), 500

@app.route('/api/debug/wordpress-test')
def debug_wordpress_test():
    """WordPress統合テスト"""
    try:
        from config.settings import load_settings
        from core.wordpress_poster import WordPressPoster
        
        # 統合処理と同じ設定読み込み
        settings = load_settings()
        wp_settings = settings.get('wordpress', {})
        
        logger.info(f"統合テスト WordPress設定: {wp_settings}")
        
        # WordPressPoster作成とテスト
        poster = WordPressPoster(wp_settings)
        
        # テスト用記事データ
        test_article = {
            'title': '【統合テスト】WordPress投稿テスト',
            'content': '<p>統合処理でのWordPress投稿テストです。</p>',
            'summary': '統合テスト用の記事です。'
        }
        
        # ログイン詳細テスト
        login_success = poster._login()
        
        if not login_success:
            return jsonify({
                'success': False,
                'error': 'ログイン失敗',
                'settings': {
                    'site_url': wp_settings.get('site_url'),
                    'username': wp_settings.get('username'),
                    'status': wp_settings.get('status'),
                    'timeout': wp_settings.get('timeout')
                }
            })
        
        # 投稿実行
        success = poster.post_article(test_article)
        
        return jsonify({
            'success': success,
            'login_success': login_success,
            'settings': {
                'site_url': wp_settings.get('site_url'),
                'username': wp_settings.get('username'),
                'status': wp_settings.get('status'),
                'timeout': wp_settings.get('timeout')
            }
        })
        
    except Exception as e:
        logger.error(f"統合テストエラー: {e}")
        import traceback
        logger.error(f"トレースバック: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

def process_podcast_background(task_id: str, file_url: str, episode_url: str, user_settings: dict):
    """バックグラウンドでポッドキャスト処理"""
    try:
        from config.settings import load_settings
        from core.podcast_processor import PodcastProcessor
        from core.blog_generator import BlogGenerator
        from core.wordpress_poster import WordPressPoster
        import datetime
        
        # デフォルト設定をロード
        default_settings = load_settings()
        
        # ユーザー設定をマージ
        merged_settings = default_settings.copy()
        for key, value in user_settings.items():
            if key in merged_settings and isinstance(merged_settings[key], dict):
                merged_settings[key].update(value)
            else:
                merged_settings[key] = value
        
        def update_status(step, total, step_name, status_msg, error=None):
            timestamp = datetime.datetime.now().strftime('%H:%M:%S')
            if not hasattr(app, 'processing_status'):
                app.processing_status = {}
            
            if task_id not in app.processing_status:
                app.processing_status[task_id] = {'logs': []}
            
            app.processing_status[task_id].update({
                'current_step': step,
                'total_steps': total,
                'step_name': step_name,
                'status': status_msg,
                'error': error,
                'timestamp': timestamp
            })
            
            app.processing_status[task_id]['logs'].append({
                'timestamp': timestamp,
                'level': 'ERROR' if error else 'INFO',
                'message': error if error else status_msg
            })
            
            logger.info(f"[{task_id}] {step_name}: {status_msg}")
        
        # Step 1: 音声ダウンロード
        update_status(1, 4, '音声ダウンロード', f'音声をダウンロード中: {file_url}')
        processor = PodcastProcessor()
        audio_path = processor.download_audio(file_url)
        update_status(1, 4, '音声ダウンロード', '音声ダウンロード完了')
        
        # Step 2: 文字起こし
        update_status(2, 4, '文字起こし', 'Whisperで文字起こし中...')
        transcript = processor.transcribe_audio(audio_path, merged_settings.get('whisper', {}))
        update_status(2, 4, '文字起こし', f'文字起こし完了: {len(transcript)}文字')
        
        # Step 3: ブログ記事生成
        update_status(3, 4, 'ブログ記事生成', 'Claude AIで記事生成中...')
        generator = BlogGenerator(merged_settings)
        article_data = generator.generate_article(transcript, episode_url)
        update_status(3, 4, 'ブログ記事生成', f'記事生成完了: {article_data["title"]}')
        
        # 結果を先に保存（WordPress投稿に失敗しても記事は保存）
        try:
            logger.info(f"[{task_id}] 記事データ保存開始")
            app.processing_status[task_id]['result'] = article_data
            logger.info(f"[{task_id}] 記事データ保存完了: {len(str(article_data))}文字")
        except Exception as save_error:
            logger.error(f"[{task_id}] 記事データ保存エラー: {save_error}")
            import traceback
            logger.error(f"[{task_id}] 保存エラートレースバック: {traceback.format_exc()}")
            raise
        
        # Step 4: WordPress投稿
        update_status(4, 4, 'WordPress投稿', 'WordPress投稿中...')
        
        # WordPress設定をチェック
        wp_settings = merged_settings.get('wordpress', {})
        logger.info(f"[{task_id}] WordPress設定確認: site_url={bool(wp_settings.get('site_url'))}, username={bool(wp_settings.get('username'))}, password={bool(wp_settings.get('password'))}")
        logger.info(f"[{task_id}] WordPress設定詳細: site_url={wp_settings.get('site_url', 'None')[:20]}..., username={wp_settings.get('username', 'None')}")
        
        if wp_settings.get('site_url') and wp_settings.get('username') and wp_settings.get('password'):
            try:
                logger.info(f"[{task_id}] WordPressPoster初期化開始")
                poster = WordPressPoster(wp_settings)
                logger.info(f"[{task_id}] WordPressPoster初期化完了")
                
                logger.info(f"[{task_id}] WordPress投稿処理開始")
                wp_success = poster.post_article(article_data)
                logger.info(f"[{task_id}] WordPress投稿処理完了: {wp_success}")
                
                if wp_success:
                    update_status(4, 4, '完了', 'すべての処理が完了しました！WordPress投稿成功')
                    logger.info(f"[{task_id}] WordPress投稿成功")
                else:
                    update_status(4, 4, '完了', '記事生成は完了しましたが、WordPress投稿に失敗しました')
                    logger.warning(f"[{task_id}] WordPress投稿失敗")
            except Exception as wp_error:
                import traceback
                error_msg = f"WordPress投稿エラー: {str(wp_error)}"
                trace_msg = traceback.format_exc()
                update_status(4, 4, '完了', f'記事生成完了（WordPress投稿エラー: {str(wp_error)}）')
                logger.error(f"[{task_id}] {error_msg}")
                logger.error(f"[{task_id}] トレースバック: {trace_msg}")
        else:
            update_status(4, 4, '完了', '記事生成完了（WordPress設定なしのため投稿はスキップ）')
            logger.info(f"[{task_id}] WordPress設定不完全のため投稿スキップ")
            logger.info(f"[{task_id}] 不完全な設定: site_url={bool(wp_settings.get('site_url'))}, username={bool(wp_settings.get('username'))}, password={bool(wp_settings.get('password'))}")
        
    except Exception as e:
        error_msg = f"処理エラー: {str(e)}"
        logger.error(f"[{task_id}] {error_msg}")
        
        if not hasattr(app, 'processing_status'):
            app.processing_status = {}
        
        if task_id in app.processing_status:
            # 記事データがある場合は保存する（途中で失敗した場合でも）
            if 'article_data' in locals():
                app.processing_status[task_id]['result'] = article_data
                logger.info(f"[{task_id}] エラー発生時でも記事データを保存しました")
            
            app.processing_status[task_id].update({
                'error': error_msg,
                'status': '処理中にエラーが発生しました'
            })
            app.processing_status[task_id]['logs'].append({
                'timestamp': datetime.datetime.now().strftime('%H:%M:%S'),
                'level': 'ERROR',
                'message': error_msg
            })

if __name__ == '__main__':
    # 必要なディレクトリを作成
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    os.makedirs('config', exist_ok=True)
    
    # Claude API キーの確認
    if not get_api_key():
        logger.error("ANTHROPIC_API_KEY環境変数が設定されていません")
        logger.info("環境変数を設定してください: export ANTHROPIC_API_KEY=your-api-key")
        exit(1)
    
    logger.info("🚀 Podcast to Blog - Web版を起動中...")
    app.run(debug=True, host='0.0.0.0', port=8003)