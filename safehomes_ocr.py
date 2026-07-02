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

        if not ocr_text or not ocr_text.strip():
            analysis_result["summary_message"] = "📸 [서류 미제출] 현재 등기부등본이나 계약서가 첨부되지 않아 시세 및 공공데이터 분석만 진행되었습니다. 더 정확한 권리 분석(근저당, 압류 등)을 원하시면 등기부등본이나 임대차계약서 사진을 채팅창에 올려주세요."
            analysis_result["is_safe"] = True  # We don't want to trigger danger just because it's missing, let public API handle the danger flags for now
            return analysis_result

        # 1. 소유자 파싱
        owner_match = self.patterns['owner'].search(ocr_text)
        if owner_match:
            analysis_result["owner_name"] = owner_match.group(1)

        # 특수 위험 키워드 (SSS급 위험 - 100대 악질 키워드 + 숨은 사기 키워드)
        risk_keywords = [
            "신탁", "담보신탁", "처분신탁", "관리신탁", "가등기", "소유권이전청구권가등기", "가처분", "처분금지가처분", "가압류", "압류", "국세", "지방세", "체납처분",
            "임의경매개시결정", "강제경매개시결정", "임차권등기명령", "전세권설정", "질권설정", "채권양도",
            "대지권미등기", "토지별도등기", "위반건축물", "불법건축물", "근린생활시설", "근생", "다중주택", "공동담보", "예고등기", "지분권자"
        ]
        danger_flags = [k for k in risk_keywords if k in ocr_text]

        # 2. 계약서 독소조항 매칭 (강화)
        toxic_keywords = [
            "현 시설물 상태", "현 상태로 인수인계", "당일 설정", "수리비 임차인 부담", "권리금 포기", 
            "전입신고 불가", "퇴거", "소송비용 임차인 부담", "임대인 변경에 동의", "조세채권은 임대인이",
            "전세보증보험 가입 불가", "가입은 임차인 책임", "대출불가 시 계약금은 반환하지 않는다"
        ]
        toxic_flags = [k for k in toxic_keywords if k in ocr_text]

        # 3. 채권최고액(빚) 파싱 로직 개선
        debt_matches = re.findall(r"(?:채권최고액|설정금액|차임|보증금).{0,5}금\s*([0-9,]+)\s*원", ocr_text)
        total_debt = 0
        if debt_matches:
            for match in debt_matches:
                clean_num = match.replace(",", "")
                if clean_num.isdigit():
                    total_debt += int(clean_num)
        
        # 4. 로펌급 진단 요약 메시지 생성
        summary = ""
        if "신탁" in danger_flags:
            summary += "🚨 [위험도 SSS급: 신탁 부동산] 이 부동산은 신탁회사 소유입니다. 등기부상의 임대인(위탁자)과 계약하면 전세금을 100% 날립니다. 반드시 '신탁원부'를 발급받아 임대 권한을 확인하십시오!\n"
        elif "임차권등기" in danger_flags:
            summary += "🚨 [위험도 SS급: 임차권등기명령 이력] 과거 집주인이 세입자에게 보증금을 돌려주지 않은 악질 이력이 있습니다. 절대 계약하지 마십시오.\n"
        elif any(k in danger_flags for k in ["가처분", "가압류", "대지권미등기", "토지별도등기"]):
            summary += "🚨 [위험도 SS급: 소유권 분쟁 및 등기 하자] 가처분, 가압류, 혹은 토지/건물 등기 하자가 발견되었습니다. 계약 절대 금지.\n"
        elif total_debt > 0:
            summary += f"⚠️ [위험도 A급: 선순위 근저당] 등기부상 총 {total_debt:,}원의 빚(채권최고액)이 잡혀 있습니다. 매매가와 보증금을 합산하여 깡통전세 여부를 반드시 확인하세요.\n"
        else:
            if not danger_flags and not toxic_flags:
                summary = "✅ [클린 매물] 등기부등본 및 계약서 상의 명시적인 위험 권리(가압류, 신탁 등) 및 독소조항이 발견되지 않았습니다. 단, 공공데이터(시세, 불법건축물) 분석 결과를 추가로 확인하십시오."
            else:
                summary = "⚠️ 일부 위험 요소가 탐지되었습니다. 하단의 세부 특약 및 조언을 확인하세요."

        analysis_result["summary_message"] = summary
        analysis_result["danger_flags"] = danger_flags
        analysis_result["toxic_clauses_found"] = toxic_flags
        analysis_result["total_mortgage"] = total_debt

        # 5. 경매(Auction) 특화 권리분석 로직 (말소기준권리 및 선순위 인수 폭탄 탐지)
        if contract_type == "경매":
            from datetime import datetime
            
            # (1) 날짜 + 권리 키워드 추출 (예: "2021.05.12 근저당", "2020.10.01 가처분")
            malso_keywords = ["근저당", "저당권", "가압류", "압류", "담보가등기", "경매개시결정", "전세권"]
            danger_senior_keywords = ["가처분", "소유권이전청구권가등기", "임차권", "전입신고", "지상권", "가등기"]
            
            date_pattern = re.compile(r'(20\d{2})[\.\-\/]\s*(\d{1,2})[\.\-\/]\s*(\d{1,2})[^\n]*?(근저당|저당권|가압류|압류|담보가등기|경매개시결정|전세권|가처분|가등기|임차권|전입신고|지상권)', re.IGNORECASE)
            matches = date_pattern.findall(ocr_text)
            
            malso_date = None
            malso_name = "확인 불가"
            senior_assumed_rights = []
            
            parsed_rights = []
            for match in matches:
                y, m, d, right_name = match
                try:
                    dt = datetime(int(y), int(m), int(d))
                    parsed_rights.append((dt, right_name))
                except:
                    continue
                    
            if parsed_rights:
                malso_candidates = [r for r in parsed_rights if any(k in r[1] for k in malso_keywords)]
                if malso_candidates:
                    malso_candidates.sort(key=lambda x: x[0])
                    malso_date = malso_candidates[0][0]
                    malso_name = malso_candidates[0][1]
                    
                if malso_date:
                    for r in parsed_rights:
                        if r[0] < malso_date and any(k in r[1] for k in danger_senior_keywords):
                            senior_assumed_rights.append(f"{r[0].strftime('%Y.%m.%d')} {r[1]}")
            
            warning_msg = ""
            has_assumed = False
            
            if malso_date:
                warning_msg += f"📌 [말소기준권리]: {malso_date.strftime('%Y.%m.%d')} {malso_name}\n"
                if senior_assumed_rights:
                    has_assumed = True
                    warning_msg += f"🚨 [SSS급 인수 폭탄 발견]: 말소기준권리보다 빠른 선순위 권리({', '.join(senior_assumed_rights)})가 탐지되었습니다. 소유권 상실 위험! 입찰 절대 금지!\n"
                else:
                    warning_msg += "✅ 말소기준권리보다 앞선 선순위 (가)등기/가처분은 탐지되지 않았습니다.\n"
            else:
                warning_msg += "⚠️ 말소기준권리 날짜를 OCR로 추출하지 못했습니다. 매각물건명세서를 직접 확인하십시오.\n"
                
            special_rights = [k for k in ["유치권", "법정지상권", "분묘기지권", "예고등기"] if k in ocr_text]
            if special_rights:
                has_assumed = True
                warning_msg += f"💣 [하드코어 특수권리 탐지]: {', '.join(special_rights)}이(가) 언급되었습니다. 대법원 판례에 따라 철저한 팩트 체크 및 현장 탐문이 필요합니다."

            analysis_result["auction_analysis"] = {
                "standard_right": f"{malso_date.strftime('%Y.%m.%d')} {malso_name}" if malso_date else "확인 불가",
                "has_assumed_rights": has_assumed,
                "warning": warning_msg
            }

        # 6. 종합 평가 로직
        if total_debt > 0 or danger_flags or toxic_flags:
            analysis_result["is_safe"] = False
            
        return analysis_result

if __name__ == "__main__":
    sample_text = "소유자 김철수. 채권최고액 금 150,000,000원. 가압류. 현 시설물 상태의 계약임."
    parser = RegistryParser()
    print(parser.analyze_ocr_text(sample_text, contract_type="매매"))
