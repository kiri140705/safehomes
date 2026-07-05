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
    conn.commit()
    conn.close()

def register_user_alert(user_id, region, budget, interest_type):
    # 신규 등록은 덮어쓰지 않고 항상 새로운 알림(row)으로 추가(INSERT)합니다.
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
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
