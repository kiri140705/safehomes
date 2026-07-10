import asyncio
import threading
import sys

# Windows 콘솔 이모지 출력 에러 방지
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from notification_db import get_all_alerts_for_scanner, is_notice_sent, mark_notice_sent
from public_data_api import PublicDataFetcher
from datetime import datetime

public_fetcher = PublicDataFetcher()

async def notification_worker():
    print("[*] 🚀 SafeHomes 다중 알림 감시 프로세스(Scheduler) 가동 시작...")
    while True:
        try:
            # 1. DB에서 등록된 모든 알림 리스트업
            alerts = get_all_alerts_for_scanner()
            
            # 유저별로 모아서 발송하기 위한 딕셔너리
            user_notices_buffer = {}
            
            for user_id, region, budget, interest_type in alerts:
                if user_id not in user_notices_buffer:
                    user_notices_buffer[user_id] = []
                    
                print(f"[🔍 스캐닝] 유저: {user_id} | 지역: {region} | 분야: {interest_type}")
                
                is_rtms = "실거래" in interest_type
                is_public_housing_only = any(k in interest_type.upper() for k in ["공공임대", "LH", "SH", "청년주택", "장기전세", "국민임대", "공실", "공고"])
                
                notices = []
                if any(k in interest_type for k in ["아파트", "빌라", "전세", "월세", "매매", "상가", "네이버", "평"]) and not is_public_housing_only and not is_rtms:
                    res = public_fetcher.fetch_naver_real_estate(region, budget, interest_type)
                    if res: notices.extend(res)
                    
                is_sh_only = "SH" in interest_type.upper()
                is_lh_only = "LH" in interest_type.upper()
                
                if any(k in interest_type.upper() for k in ["공공임대", "LH", "공실", "공고", "임대"]) and not is_sh_only:
                    res = public_fetcher.fetch_lh_lease_notices(interest_type, region)
                    if res: notices.extend(res)
                    
                if any(k in interest_type.upper() for k in ["공공임대", "SH", "공실", "청년주택", "장기전세", "국민임대", "전세임대", "공고", "임대"]) and not is_lh_only:
                    res = public_fetcher.fetch_sh_vacancy_and_plans(region, interest_type)
                    if res: notices.extend(res)
                    
                if "분양" in interest_type or "청약" in interest_type:
                    res = public_fetcher.fetch_general_sales_notices(region)
                    if res: notices.extend(res)
                    
                if is_rtms:
                    res = public_fetcher.fetch_naver_rtms(region, interest_type)
                    if res: notices.extend(res)
                    res = public_fetcher.fetch_real_transaction_prices(region, interest_type, budget)
                    if res: notices.extend(res)
                        
                # 3. 새로운 공고인지 검사
                for notice in notices:
                    notice_id = notice["id"]
                    if not is_notice_sent(user_id, notice_id):
                        user_notices_buffer[user_id].append(notice)
                        mark_notice_sent(user_id, notice_id)

            # 4. 유저별 알림 폭탄 방지(Batching) 및 모의 발송
            for user_id, pending_notices in user_notices_buffer.items():
                if not pending_notices:
                    continue
                    
                total_count = len(pending_notices)
                # 알림 폭탄 방지를 위해 최대 3건까지만 전송
                display_notices = pending_notices[:3]
                
                msg = f"\n=====================================\n"
                msg += f"🔔 [SafeHomes 카카오톡 푸시 알림 모의 발송]\n"
                msg += f"수신자: {user_id}\n"
                
                if total_count > 3:
                    msg += f"⚠️ **조건에 맞는 매물이 총 {total_count}건 발견되었습니다! 알림 폭탄 방지를 위해 Top 3만 요약해 드립니다.**\n"
                
                for idx, notice in enumerate(display_notices, 1):
                    url_str = notice.get('url', '')
                    if url_str:
                        msg += f"\n[{idx}] {notice['title']}\n🔗 링크: {url_str}\n"
                    else:
                        msg += f"\n- {notice['title']}\n"
                    
                msg += f"\n발송시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                msg += f"=====================================\n"
                
                print(msg)
                
                with open("push_notification_logs.txt", "a", encoding="utf-8") as f:
                    f.write(msg)
                        
        except Exception as e:
            print(f"[!] 스케줄러 에러 발생: {e}")
            
        # 1분마다 반복 스캔
        await asyncio.sleep(60)

def start_background_scanner():
    """FastAPI 외부에서 도는 별도 스레드로 스케줄러 실행"""
    def run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(notification_worker())
        
    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()
