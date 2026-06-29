import requests
import json

class PublicDataFetcher:
    def __init__(self):
        print("[*] 세이프홈즈(SafeHomes) 공공데이터 연동 모듈 초기화...")
        # 공공데이터포털(data.go.kr) 국토교통부 건축물대장 API 키 (현재는 더미값)
        self.api_key = "YOUR_PUBLIC_DATA_API_KEY"
        self.base_url = "http://apis.data.go.kr/1613000/BldRgstService_v2/getBrBasisOlineBldInfo"

    def check_building_ledger(self, address: str):
        """
        주소를 입력받아 건축물대장 API를 조회하고,
        위반건축물(불법건축물) 여부를 반환합니다.
        """
        print(f"[*] '{address}' 주소의 건축물대장 실시간 조회를 시작합니다...")
        
        # 실제 환경에서는 주소를 법정동코드(sigunguCd, bjdongCd)로 변환하는 카카오 로컬 API 연동이 선행되어야 함
        # 현재는 공모전 제출용 구조 뼈대 작성
        
        # TODO: 실제 API 호출 로직으로 교체
        # params = {
        #     "serviceKey": self.api_key,
        #     "sigunguCd": "11680", # 예: 강남구
        #     "bjdongCd": "10100",  # 예: 역삼동
        #     "platGbCd": "0",
        #     "bun": "0001",
        #     "ji": "0000",
        #     "_type": "json"
        # }
        # response = requests.get(self.base_url, params=params)
        
        # 임시 결과 (위반건축물 적발 케이스 시뮬레이션)
        mock_response = {
            "address": address,
            "is_illegal_building": True,  # 위반건축물 여부 (True면 전세 대출 불가)
            "violation_details": "옥상 불법 증축 (2022년 적발)",
            "building_type": "다세대주택"
        }
        
        return mock_response
        
    def get_market_price_risk(self, address: str, deposit: int):
        """
        주변 실거래가 데이터를 조회하여 사용자가 입력한 전세 보증금(deposit)과 비교,
        전세가율(깡통전세 위험도)을 계산합니다.
        """
        print(f"[*] '{address}' 주소의 실거래가 및 깡통전세 위험도 계산 중...")
        
        # 가상의 주변 평균 매매가 (실제로는 실거래가 API 연동)
        avg_sale_price = 200000000  # 2억 원
        
        jeonse_rate = (deposit / avg_sale_price) * 100
        is_kangtong = jeonse_rate >= 80.0  # 전세가율 80% 이상이면 위험
        
        return {
            "avg_sale_price": avg_sale_price,
            "jeonse_rate": round(jeonse_rate, 1),
            "is_kangtong_risk": is_kangtong
        }

if __name__ == "__main__":
    fetcher = PublicDataFetcher()
    
    # 1. 건축물대장 (위반건축물) 테스트
    ledger_info = fetcher.check_building_ledger("서울특별시 강서구 화곡동 123-4")
    print("\n[🏛️ 건축물대장 분석 결과]")
    if ledger_info["is_illegal_building"]:
        print(f"🚨 위반건축물로 등록되어 있습니다! ({ledger_info['violation_details']}) -> 전세자금대출 불가 가능성 높음")
    
    # 2. 깡통전세 (실거래가) 테스트 - 보증금 1억 8천만원
    price_info = fetcher.get_market_price_risk("서울특별시 강서구 화곡동 123-4", 180000000)
    print("\n[💰 깡통전세 위험도 결과]")
    print(f"주변 평균 매매가: {price_info['avg_sale_price']:,}원")
    print(f"해당 매물 전세가율: {price_info['jeonse_rate']}%")
    if price_info["is_kangtong_risk"]:
        print("🚨 전세가율 80% 이상! 깡통전세 고위험군입니다. 보증금 미반환 사고를 주의하세요!")
