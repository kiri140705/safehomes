import sqlite3
import os

DB_PATH = "safehomes_notifications.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1:N 다중 알림 조건 테이블 생성 (alert_id 도입)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_alerts (
            alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            target_region TEXT,
            target_budget INTEGER,
            interest_type TEXT
        )
    ''')
    # 중복 발송 방지용 히스토리 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sent_notices (
            user_id TEXT,
            notice_id TEXT,
            PRIMARY KEY (user_id, notice_id)
        )
    ''')
    # 카카오 로그인(OAuth) 토큰 저장 - 실제 "나에게 보내기" 알림 발송에 사용
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kakao_tokens (
            user_id TEXT PRIMARY KEY,
            access_token TEXT,
            refresh_token TEXT,
            expires_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_kakao_token(user_id, access_token, refresh_token, expires_at):
    """카카오 OAuth 토큰 저장/갱신 (user_id 기준 upsert)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO kakao_tokens (user_id, access_token, refresh_token, expires_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            access_token=excluded.access_token,
            refresh_token=excluded.refresh_token,
            expires_at=excluded.expires_at
    ''', (user_id, access_token, refresh_token, expires_at))
    conn.commit()
    conn.close()

def get_kakao_token(user_id):
    """저장된 카카오 OAuth 토큰 조회. 없으면 None."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT access_token, refresh_token, expires_at FROM kakao_tokens WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {"access_token": row[0], "refresh_token": row[1], "expires_at": row[2]}

def register_user_alert(user_id, region, budget, interest_type):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 공백으로 인한 중복 방지
    if isinstance(user_id, str): user_id = user_id.strip()
    if isinstance(region, str): region = region.strip()
    if isinstance(interest_type, str): interest_type = interest_type.strip()
    try:
        budget = int(budget)
    except:
        budget = 0
        
    # 중복 확인 (이미 존재하는지 SELECT)
    cursor.execute('''
        SELECT alert_id FROM user_alerts 
        WHERE user_id=? AND target_region=? AND target_budget=? AND interest_type=?
    ''', (user_id, region, budget, interest_type))
    existing = cursor.fetchone()
    
    if existing:
        alert_id = existing[0]
    else:
        cursor.execute('''
            INSERT INTO user_alerts (user_id, target_region, target_budget, interest_type)
            VALUES (?, ?, ?, ?)
        ''', (user_id, region, budget, interest_type))
        alert_id = cursor.lastrowid
        conn.commit()
        
    conn.close()
    return alert_id

def get_all_alerts_for_scanner():
    """스케줄러가 스캔할 때 쓸 전체 알림 리스트 반환"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, target_region, target_budget, interest_type FROM user_alerts")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_user_alerts(user_id):
    """특정 유저의 모든 알림 리스트업 (ListMyNotifications용)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT alert_id, target_region, target_budget, interest_type FROM user_alerts WHERE user_id=?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_specific_alert(alert_id):
    """특정 단일 알림 조회"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT alert_id, user_id, target_region, target_budget, interest_type FROM user_alerts WHERE alert_id=?", (alert_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_user_alert(alert_id, region, budget, interest_type):
    """특정 알림 조건만 수정"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE user_alerts 
        SET target_region=?, target_budget=?, interest_type=?
        WHERE alert_id=?
    ''', (region, budget, interest_type, alert_id))
    conn.commit()
    conn.close()

def delete_user_alert(alert_id):
    """특정 단일 알림 취소"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_alerts WHERE alert_id=?", (alert_id,))
    conn.commit()
    conn.close()
    
def delete_all_alerts(user_id):
    """유저의 모든 알림 취소 및 히스토리 삭제"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_alerts WHERE user_id=?", (user_id,))
    cursor.execute("DELETE FROM sent_notices WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def is_notice_sent(user_id, notice_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM sent_notices WHERE user_id=? AND notice_id=?", (user_id, notice_id))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def mark_notice_sent(user_id, notice_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO sent_notices (user_id, notice_id) VALUES (?, ?)", (user_id, notice_id))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("[*] DB Re-initialized for 1:N Architecture.")
