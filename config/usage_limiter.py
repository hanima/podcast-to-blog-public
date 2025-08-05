#!/usr/bin/env python3
"""
利用制限管理モジュール
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from config.settings import CONFIG_DIR, USAGE_LOG_FILE

class UsageLimiter:
    def __init__(self, daily_limit=5):
        self.daily_limit = daily_limit
        self.log_file = USAGE_LOG_FILE
        
    def get_today_key(self):
        """今日の日付キーを取得（JST）"""
        jst_now = datetime.utcnow() + timedelta(hours=9)
        return jst_now.strftime("%Y-%m-%d")
    
    def load_usage_log(self):
        """利用ログを読み込み"""
        try:
            if self.log_file.exists():
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception:
            return {}
    
    def save_usage_log(self, log_data):
        """利用ログを保存"""
        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
    
    def get_usage_info(self, client_ip=None):
        """利用状況を取得"""
        today_key = self.get_today_key()
        log_data = self.load_usage_log()
        
        # 今日のデータを取得
        today_data = log_data.get(today_key, {"total": 0, "ips": {}})
        
        # IP別の利用回数（IP制限は今回は簡易的にスキップ）
        total_used = today_data.get("total", 0)
        remaining = max(0, self.daily_limit - total_used)
        
        # 次回リセット時間（JST）
        jst_now = datetime.utcnow() + timedelta(hours=9)
        next_reset = jst_now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        
        return {
            "total_used": total_used,
            "daily_limit": self.daily_limit,
            "remaining": remaining,
            "can_use": remaining > 0,
            "next_reset": next_reset.strftime("%Y-%m-%d %H:%M:%S JST"),
            "next_reset_iso": next_reset.isoformat()
        }
    
    def use_quota(self, client_ip=None):
        """利用回数を消費"""
        usage_info = self.get_usage_info(client_ip)
        
        if not usage_info["can_use"]:
            return False, "利用上限に達しました"
        
        # ログを更新
        today_key = self.get_today_key()
        log_data = self.load_usage_log()
        
        if today_key not in log_data:
            log_data[today_key] = {"total": 0, "ips": {}}
        
        log_data[today_key]["total"] += 1
        
        # IP別記録（オプション）
        if client_ip:
            if client_ip not in log_data[today_key]["ips"]:
                log_data[today_key]["ips"][client_ip] = 0
            log_data[today_key]["ips"][client_ip] += 1
        
        # 古いログを削除（7日以上前）
        self.cleanup_old_logs(log_data)
        
        # 保存
        if self.save_usage_log(log_data):
            return True, "利用回数を記録しました"
        else:
            return False, "利用記録の保存に失敗しました"
    
    def cleanup_old_logs(self, log_data):
        """古いログを削除"""
        cutoff_date = datetime.utcnow() + timedelta(hours=9) - timedelta(days=7)
        cutoff_key = cutoff_date.strftime("%Y-%m-%d")
        
        keys_to_remove = [key for key in log_data.keys() if key < cutoff_key]
        for key in keys_to_remove:
            del log_data[key]