import re
import json

class RegistryParser:
    def __init__(self):
        print("[*] 세이프홈즈(SafeHomes) 등기부등본 텍스트 분석기 초기화...")
        # 등기부등본의 주요 항목을 찾아내기 위한 정규표현식 패턴
        self.patterns = {
            "owner": re.compile(r'소유자\s*([가-힣]{2,5})', re.IGNORECASE),
            # 근저당권 설정 금액(채권최고액) 추출: "채권최고액 금 150,000,000원" 등
            "mortgage": re.compile(r'채권최고액\s*금\s*([\d,]+)\s*원', re.IGNORECASE),
            # 신탁, 압류, 가압류 등 위험 키워드 탐지
            "danger_keywords": re.compile(r'(신탁|가압류|압류|경매개시|임차권등기)', re.IGNORECASE)
        }

    def analyze_ocr_text(self, ocr_text: str):
        """
        Vision AI(OCR)를 통해 추출된 등기부등본 텍스트(문자열)를 분석하여
        매매 및 전세 계약 시 필요한 핵심 위험 요소를 JSON 형태로 추출합니다.
        """
        print("[*] 등기부등본 텍스트 분석을 시작합니다...")
        
        analysis_result = {
            "owner_name": "미상",
            "total_mortgage": 0,
            "danger_flags": [],
            "is_safe": True,
            "summary_message": ""
        }

        # 1. 소유자 파싱 (갑구)
        owner_match = self.patterns['owner'].search(ocr_text)
        if owner_match:
            analysis_result["owner_name"] = owner_match.group(1)

        # 2. 채권최고액 총합 계산 (을구)
        mortgage_matches = self.patterns['mortgage'].findall(ocr_text)
        total_debt = 0
        for amount_str in mortgage_matches:
            # 쉼표 제거 후 숫자로 변환
            clean_num = int(amount_str.replace(',', ''))
            total_debt += clean_num
        analysis_result["total_mortgage"] = total_debt

        # 3. 위험 키워드 (신탁, 가압류 등) 탐지
        danger_matches = self.patterns['danger_keywords'].findall(ocr_text)
        # 중복 제거
        danger_flags = list(set(danger_matches))
        if danger_flags:
            analysis_result["danger_flags"] = danger_flags

        # 4. 종합 평가 로직
        if total_debt > 0 or danger_flags:
            analysis_result["is_safe"] = False
            
        # 5. 리포트 메시지 생성
        report = []
        if analysis_result["owner_name"] != "미상":
            report.append(f"✅ 등기상 소유자는 '{analysis_result['owner_name']}'님입니다. 실제 집주인 신분증과 반드시 대조하세요.")
        
        if total_debt > 0:
            formatted_debt = format(total_debt, ',')
            report.append(f"⚠️ [주의] 을구에 총 {formatted_debt}원의 근저당(빚)이 설정되어 있습니다. 깡통전세 위험이 있습니다!")
            
        if danger_flags:
            report.append(f"🚨 [초고위험] 등기부에 {', '.join(danger_flags)} 내역이 발견되었습니다. 매매/전세 계약을 절대 진행하지 마세요!")
            
        if analysis_result["is_safe"]:
            report.append("✅ 현재 텍스트 상으로는 근저당이나 압류 내역이 발견되지 않았습니다. (깨끗한 등기)")
            
        analysis_result["summary_message"] = "\n".join(report)
        
        return analysis_result

if __name__ == "__main__":
    # 테스트용 가짜 OCR 텍스트 (실제로는 이미지에서 추출된 텍스트가 들어옴)
    sample_ocr_text = """
    [표제부] (1동의 건물의 표시) ...
    [갑구] (소유권에 관한 사항)
    순위번호 1. 소유권이전. 소유자 김철수.
    [을구] (소유권 이외의 권리에 관한 사항)
    순위번호 1. 근저당권설정. 채권최고액 금 150,000,000원. 채무자 김철수. 근저당권자 주식회사 국민은행.
    순위번호 2. 가압류. 청구금액 금 50,000,000원. 채권자 이영희.
    """
    
    parser = RegistryParser()
    result = parser.analyze_ocr_text(sample_ocr_text)
    
    print("\n[📊 세이프홈즈 분석 결과]")
    print(result["summary_message"])
    print(f"\nRAW JSON: {json.dumps(result, ensure_ascii=False, indent=2)}")
