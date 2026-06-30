# -*- coding: utf-8 -*-
import re
import json

class RegistryParser:
    def __init__(self):
        print("[*] 세이프홈즈(SafeHomes) 등기부등본 및 계약서 텍스트 분석기 초기화...")
        self.patterns = {
            "owner": re.compile(r'소유자\s*([가-힣]{2,5})', re.IGNORECASE),
            "mortgage": re.compile(r'채권최고액\s*금\s*([\d,]+)\s*원', re.IGNORECASE),
            "danger_keywords": re.compile(r'(신탁|가압류|압류|경매개시|임차권등기|가처분|예고등기|유치권)', re.IGNORECASE),
            "toxic_clauses": re.compile(r'(현\s*시설물\s*상태|수리\s*불가|위약금\s*전액|권리금\s*포기|권리금\s*인정\s*안함|임대인의\s*매매에\s*무조건\s*협조)', re.IGNORECASE)
        }

    def analyze_ocr_text(self, ocr_text: str, contract_type: str = "전세", property_type: str = "주택"):
        """
        OCR 텍스트를 분석하여 등기부등본의 위험 요소와 가계약서의 독소조항을 탐지합니다.
        경매(Auction) 모드일 경우 권리분석(말소기준권리 등)을 추가로 수행합니다.
        """
        print(f"[*] {property_type} {contract_type} 텍스트 분석을 시작합니다...")
        
        analysis_result = {
            "owner_name": "미상",
            "total_mortgage": 0,
            "danger_flags": [],
            "toxic_clauses_found": [],
            "auction_analysis": {},
            "is_safe": True,
            "summary_message": ""
        }

        # 1. 소유자 파싱
        owner_match = self.patterns['owner'].search(ocr_text)
        if owner_match:
            analysis_result["owner_name"] = owner_match.group(1)

        # 2. 채권최고액 총합 계산
        mortgage_matches = self.patterns['mortgage'].findall(ocr_text)
        total_debt = 0
        for amount_str in mortgage_matches:
            clean_num = int(amount_str.replace(',', ''))
            total_debt += clean_num
        analysis_result["total_mortgage"] = total_debt

        # 3. 등기부 위험 키워드 탐지
        danger_matches = self.patterns['danger_keywords'].findall(ocr_text)
        danger_flags = list(set(danger_matches))
        if danger_flags:
            analysis_result["danger_flags"] = danger_flags

        # 4. 계약서 독소조항 탐지
        toxic_matches = self.patterns['toxic_clauses'].findall(ocr_text)
        toxic_flags = list(set(toxic_matches))
        if toxic_flags:
            analysis_result["toxic_clauses_found"] = toxic_flags

        # 5. 경매(Auction) 특화 권리분석 로직
        if contract_type == "경매":
            # 실제로는 날짜를 파싱하여 말소기준권리를 찾아야 하나, 해커톤 시연용으로 휴리스틱 분석 적용
            analysis_result["auction_analysis"] = {
                "standard_right": "근저당권 (확인 필요)",
                "has_assumed_rights": False, # 낙찰자 인수 권리 여부
                "warning": ""
            }
            if "가처분" in danger_flags or "유치권" in danger_flags:
                analysis_result["auction_analysis"]["has_assumed_rights"] = True
                analysis_result["auction_analysis"]["warning"] = "말소기준권리보다 앞선 가처분 또는 유치권 신고가 탐지되었습니다. 낙찰자가 전액 인수해야 할 수 있습니다!"

        # 6. 종합 평가 로직
        if total_debt > 0 or danger_flags or toxic_flags:
            analysis_result["is_safe"] = False
            
        return analysis_result

if __name__ == "__main__":
    sample_text = "소유자 김철수. 채권최고액 금 150,000,000원. 가압류. 현 시설물 상태의 계약임."
    parser = RegistryParser()
    print(parser.analyze_ocr_text(sample_text, contract_type="매매"))
