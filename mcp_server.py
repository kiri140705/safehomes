# -*- coding: utf-8 -*-
import json
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from typing import Annotated
from safehomes_ocr import RegistryParser
from public_data_api import PublicDataFetcher
from mcp.server.transport_security import TransportSecuritySettings

# Initialize the FastMCP Server
mcp = FastMCP(
    "safehomes",
    stateless_http=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False)
)
ocr_parser = RegistryParser()
public_fetcher = PublicDataFetcher()

@mcp.tool(
    name="AnalyzeRealEstateSafety",
    description="Analyzes real estate safety risks across all properties (Residential, Commercial, KIC, Land, Hotels, Officetels) using OCR and public APIs.",
    annotations={
        "title": "SafeHomes MAX: 통합 부동산 AI 법무사",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
def analyze_real_estate_safety(
    address: Annotated[str, Field(description="진단할 부동산의 주소. 모를 경우 '전국'")] = "전국",
    deposit: Annotated[int, Field(description="계약 예정인 매매대금 또는 전/월세 보증금 (단위: 만원). 모를 경우 0")] = 0,
    contract_type: Annotated[str, Field(description="계약 종류 ('매매', '전세', '월세', '경매' 중 택1). 모를 경우 '매매'")] = "매매",
    property_type: Annotated[str, Field(description="매물 종류 ('주택', '상가', '오피스텔', '지식산업센터', '빌딩/통상가', '숙박업(호텔/펜션)', '재개발(입주권)', '토지(전/답)', '임야(산/묘지)' 중 택1). 모를 경우 '주택'")] = "주택",
    ocr_text: Annotated[str, Field(description="등기부등본 및 계약서의 전체 OCR 추출 텍스트. 유저가 이미지나 문서를 제공하지 않은 경우 반드시 빈 문자열('')을 입력하세요.")] = "",
    current_status: Annotated[str, Field(description="현재 진행 상태 ('계약 전', '계약 중', '사고 발생/분쟁' 중 택1)")] = "계약 전",
    monthly_rent: Annotated[int, Field(description="월세 금액 (단위: 만원)")] = 0,
    business_type: Annotated[str, Field(description="상가/지산일 경우 희망 업종 (유저가 입력하지 않았다면 '일반업종'으로 추출할 것)")] = "",
    intent: Annotated[str, Field(description="유저의 질의 의도 ('사기 방어 및 계약 분석', '거시경제 및 집값 동향', '청약 및 가점 전략', '일반 부동산 상담 및 팩트폭행' 중 택1)")] = "일반 부동산 상담 및 팩트폭행",
    homeless_years: Annotated[int, Field(description="유저의 무주택 기간 (단위: 년. 모르면 0)")] = 0,
    subscription_years: Annotated[int, Field(description="유저의 청약통장 가입 기간 (단위: 년. 모르면 0)")] = 0,
    dependents: Annotated[int, Field(description="유저의 본인 제외 부양가족 수 (아내 1명, 자녀 2명이면 총 3명. 모르면 0)")] = 0,
    user_query: Annotated[str, Field(description="유저가 실제 입력한 질문 원본 텍스트 전체. 요약하지 말고 그대로 넘길 것. 모르면 ''")] = "",
) -> str:
    # 0. 인텐트 동적 라우팅 (거시경제 / 청약 / 사기 방어 / 일반 상담)
    if intent == "일반 부동산 상담 및 팩트폭행":
        general_advice = public_fetcher.get_general_advice(user_query)
        return json.dumps({
            "status": "INFO",
            "diagnostic_summary": general_advice,
            "market_price_analysis": "해당 모드 생략",
            "building_ledger_analysis": "해당 모드 생략",
            "brokerage_fee_limit": "",
            "recommended_safe_clauses": [],
            "field_inspection_checklist": [],
            "negotiation_message": "",
            "public_housing_alternatives": [],
            "dispute_resolution_guide": []
        }, ensure_ascii=False)
    if intent == "거시경제 및 집값 동향":
        macro_report = public_fetcher.get_macro_real_estate_stats(address)
        return json.dumps({
            "status": "INFO",
            "diagnostic_summary": macro_report,
            "market_price_analysis": "해당 모드 생략",
            "building_ledger_analysis": "해당 모드 생략",
            "brokerage_fee_limit": "",
            "recommended_safe_clauses": [],
            "field_inspection_checklist": [],
            "negotiation_message": "",
            "public_housing_alternatives": [],
            "dispute_resolution_guide": []
        }, ensure_ascii=False)
        
    if intent == "청약 및 가점 전략":
        applyhome_report = public_fetcher.get_applyhome_subscription_info(address, deposit, homeless_years, subscription_years, dependents)
        if not applyhome_report:
            applyhome_report = "해당 자본/가점 조건으로 조회 가능한 최적의 청약 정보가 없습니다."
        return json.dumps({
            "status": "INFO",
            "diagnostic_summary": applyhome_report,
            "market_price_analysis": "해당 모드 생략",
            "building_ledger_analysis": "해당 모드 생략",
            "brokerage_fee_limit": "",
            "recommended_safe_clauses": [],
            "field_inspection_checklist": [],
            "negotiation_message": "",
            "public_housing_alternatives": [],
            "dispute_resolution_guide": []
        }, ensure_ascii=False)

    # 1. 기존 사기 방어 및 계약 분석 모드
    ocr_result = ocr_parser.analyze_ocr_text(ocr_text, contract_type, property_type)
    ledger_result = public_fetcher.check_building_ledger(address, property_type, business_type)
    flood_result = public_fetcher.check_flood_risk(address)
    price_result = public_fetcher.get_market_price_risk(address, deposit, monthly_rent, contract_type, property_type, ocr_result.get("total_mortgage", 0))
    
    # 종합 위험도 판정
    is_danger = not ocr_result["is_safe"] or ledger_result["is_illegal_building"] or price_result["is_kangtong_risk"]
    
    # 리턴 데이터 구조 초기화
    safe_clauses = []
    field_inspection_checklist = []
    negotiation_message = ""
    public_housing_alternatives = []
    dispute_resolution_guide = []
    
    # ==========================================
    # 모드 1: 탐색 및 공격 (대안 추천)
    # ==========================================
    if is_danger or price_result["is_kangtong_risk"]:
        public_housing_alternatives = public_fetcher.get_public_housing_alternatives(property_type, deposit, address, is_danger)
    else:
        # 안전한 매물이라도 청약 스나이퍼 라우팅은 백그라운드로 작동시킴
        applyhome_msg = public_fetcher.get_applyhome_subscription_info(address, deposit, homeless_years, subscription_years, dependents)
        if applyhome_msg:
            public_housing_alternatives.append(applyhome_msg)

    # ==========================================
    # 모드 2: 사후 구제 및 분쟁 해결 (Rescue)
    # ==========================================
    if current_status == "사고 발생/분쟁":
        if contract_type in ["전세", "월세"]:
            dispute_resolution_guide.append("🚨 [절대 금지] 이사 가거나 전입신고를 빼면 우선변제권을 상실합니다. 현재 상태를 유지하세요.")
            dispute_resolution_guide.append("1. [임차권등기명령 신청]: 법원에 즉시 임차권등기명령을 신청하세요. 등기부등본에 등재된 후 이사하셔야 합니다.")
            dispute_resolution_guide.append("2. [내용증명 발송]: 임대차계약 해지 및 보증금 반환 촉구 내용증명서를 작성하여 우체국을 통해 발송하세요.")
            if contract_type == "월세":
                dispute_resolution_guide.append("3. [동시이행의 항변권]: 보증금을 돌려받지 못했다면 월세를 내지 않고 거주할 권리가 있습니다.")
            dispute_resolution_guide.append("4. [HUG 보증이행 청구]: 보증보험 가입자라면 임차권등기 완료 및 내용증명 도달 후 HUG 관할 지사에 대위변제를 신청하세요.")
            
        elif contract_type == "매매":
            dispute_resolution_guide.append("1. [매도인의 하자담보책임]: 누수 등 중대 하자는 안 날로부터 6개월 이내에 전 집주인(매도인)에게 수리비 청구가 가능합니다.")
            dispute_resolution_guide.append("2. [증거 수집]: 즉시 누수 부위의 사진/동영상을 촬영하고, 수리 기사의 소견서와 견적서를 확보하세요.")
            dispute_resolution_guide.append("3. [공인중개사 책임]: 중개대상물 확인설명서에 하자가 기재되지 않았다면 중개사에게도 공동 책임을 물을 수 있습니다.")
            
        elif contract_type == "경매":
            dispute_resolution_guide.append("1. [부동산 인도명령]: 점유자가 퇴거를 거부할 경우, 매각대금 납부 후 6개월 이내에 법원에 '부동산 인도명령'을 신청하세요. 명도소송보다 훨씬 빠릅니다.")
            dispute_resolution_guide.append("2. [강제집행 신청]: 인도명령 결정문 송달 후에도 거부하면 관할 법원 집행관 사무소에 강제집행(계고장 부착)을 신청하세요.")
            
        elif property_type in ["상가", "빌딩/통상가", "지식산업센터"]:
            dispute_resolution_guide.append("1. [권리금 회수 방해 금지]: 건물주가 신규 임차인과의 계약을 거절하거나 과도한 월세 인상으로 권리금 회수를 방해하는 것은 상가임대차보호법 위반입니다.")
            dispute_resolution_guide.append("2. [손해배상청구소송]: 방해 행위에 대한 증거(문자, 녹취 등)를 수집하여 건물주를 상대로 '권리금 손해배상청구소송'을 제기하세요.")

    # ==========================================
    # 모드 3: 방어 (계약 중 안전 특약 생성)
    # ==========================================
    else:
        # 공통 방어 특약
        safe_clauses.append("임대인(매도인)은 계약 시 국세 및 지방세 완납 증명서를 교부한다. 미납 세금이 확인될 경우 계약을 해제할 수 있다.")
        
        # 1. 주거용 로직
        if property_type == "주택":
            if ledger_result["is_dagagu"]:
                safe_clauses.append("임대인은 잔금일 전까지 타 세대의 전입세대열람내역 및 확정일자 부여 현황 서류를 임차인에게 교부한다.")
            if contract_type in ["전세", "월세"]:
                safe_clauses.append("잔금 지급일 익일 23시 59분까지 현재 등기부등본 상태를 유지하며, 임대인은 근저당권 설정을 하지 않는다. 위반 시 배액배상한다.")
                if not price_result["hug_eligible"]:
                    safe_clauses.append("🚨 [경고] 전세가율 90% 초과로 HUG 보증보험 가입이 불가한 매물입니다.")
                    
        # 2. 오피스텔 특화 로직
        elif property_type == "오피스텔":
            if contract_type in ["전세", "월세"]:
                if "전입신고 불가" in ocr_text or "전입불가" in ocr_text:
                    safe_clauses.append("🚨 [절대 위험] 임대인이 다주택자 세금 회피를 위해 전입신고 불가를 요구하고 있습니다. 우선변제권을 잃게 되므로 절대 계약하지 마세요.")
                safe_clauses.append("임대인은 임차인의 전입신고 및 확정일자 부여를 절대 방해하지 않으며, 전입신고 불가 특약은 주택임대차보호법 위반으로 원천 무효로 한다.")
                safe_clauses.append("잔금 지급일 익일 23시 59분까지 현재 등기부등본 상태를 유지하며, 임대인은 근저당권 설정을 하지 않는다.")
            elif contract_type == "매매":
                safe_clauses.append("잔금일 기준 본 오피스텔의 과세 용도(주거용/업무용)에 대한 모든 귀책사유는 매도인에게 있으며, 허위 고지로 인한 취득세 중과/종부세 등 세금 폭탄 발생 시 매도인이 전액 배상한다.")
                safe_clauses.append("본 계약은 사업상 포괄양수도 계약으로 진행하며, 부가세 문제 발생 시 매도인이 책임진다.")
                
        # 3. 지식산업센터 (입주업종)
        elif property_type == "지식산업센터":
            if not ledger_result["business_license_ok"]:
                safe_clauses.append(f"🚨 [입주 불가 경고] 입력하신 업종({business_type})은 지식산업센터 입주 제한 업종일 가능성이 높습니다.")
                safe_clauses.append("산업집적법 위반에 따른 입주 불가 및 구청 퇴거 명령 발생 시, 본 계약은 전면 무효로 하고 위약금을 청구한다.")
        
        # 4. 숙박업(호텔/펜션)
        elif property_type == "숙박업(호텔/펜션)":
            if ledger_result["remodeling_risk"]:
                safe_clauses.append("🚨 [리모델링 주의] 현재 해당 지역의 법정 용적률/건폐율이 과거보다 하향되었습니다. 허물고 다시 지을 경우 현재 건물보다 작게 지어야 합니다.")
            safe_clauses.append("과거 불법 증축 등의 귀책사유로 숙박업 영업승계 인허가가 불가능할 경우 본 계약은 원천 무효로 한다.")
            
        # 5. 빌딩/통상가 매매
        elif property_type == "빌딩/통상가":
            safe_clauses.append("매도인은 잔금일 전까지 모든 임차인의 명도(퇴거)를 책임지며, 명도 실패 시 매수인은 즉각 계약을 해제할 수 있다.")
            
        # 6. 재개발(입주권)
        elif property_type == "재개발(입주권)":
            safe_clauses.append("매도인의 다물권자 여부 등 귀책사유로 인해 매수자에게 조합원 입주권이 미발생(현금청산)할 경우, 계약을 전면 해제하고 매매대금 전액을 반환한다.")
            
        # 7. 토지 및 임야
        elif property_type in ["토지(전/답)", "임야(산/묘지)"]:
            if ledger_result["land_restriction"]:
                safe_clauses.append(f"🚨 [경고] 해당 부지는 {ledger_result['land_restriction']}으로 건축 인허가가 불가능할 수 있습니다.")
                safe_clauses.append("해당 부지의 건축 인허가 불가 시 본 계약은 원천 무효로 한다.")
            if property_type == "임야(산/묘지)":
                safe_clauses.append("계약 체결 전 고지하지 않은 타인의 분묘기지권 발견 시, 매도인의 비용으로 즉시 이장하거나 불이행 시 계약을 해제한다.")
                
        # 상업용 공통 방어 (상가, 통상가 등)
        if property_type in ["상가", "빌딩/통상가", "숙박업(호텔/펜션)"]:
            if ledger_result["septic_tank_warning"]:
                safe_clauses.append("영업 허가에 필요한 정화조 용량 부족으로 발생하는 하수도 원인자부담금은 임대인(매도인)이 전액 부담한다.")
            if not price_result["commercial_protection_ok"]:
                safe_clauses.append("🚨 [경고] 환산보증금이 기준을 초과하여 상가임대차보호법의 일부만 적용받습니다.")

        # 100대 매물별 초정밀 임장 체크리스트 매트릭스 (팩트폭행 액션 플랜)
        INSPECTION_MATRIX = {
            "상가": [
                "🔥 [정화조/전기 증설]: 구청 환경과에 전화해 건물 전체 '정화조 용량'이 꽉 찼는지 확인하십시오. (꽉 찼다면 하수도 원인자부담금 수천만 원 덤터기). 배전반을 열어 계약 전력이 몇 kW인지 필수 확인.",
                "🔥 [위반건축물 점검]: 1층 테라스 샷시나 데크가 박혀있다면 99% 불법입니다. 이행강제금이 1년에 얼마 나오는지 정부24에서 건축물대장 떼서 노란 딱지 확인 필수.",
                "🔥 [권리금 사기]: 전 임차인이 넘기는 에어컨/냉장고가 '렌탈' 제품인지 시리얼 넘버로 확인하십시오. 렌탈이면 나중에 기계 다 뺏깁니다."
            ],
            "토지(전/답)": [
                "🔥 [맹지 사기 방어]: 현장에 가서 지적도 어플을 켜고, 내 땅으로 들어가는 '도로'가 남의 사유지(맹지)인지 확인하십시오. 알박기 당하면 건축 허가가 원천 차단됩니다.",
                "🔥 [농취증/명인방법]: 외지인의 경우 농취증 반려 리스크가 큽니다. 밭에 수목(농작물)이 있다면 '명인방법' 표시가 되어있는지 점검하십시오. 남의 나무면 베어내지도 못합니다."
            ],
            "임야(산/묘지)": [
                "🔥 [문화재/암반 폭탄]: 주변에 문화재보호구역 표지판이 있는지 확인하십시오. 땅 파다가 기왓조각 나오면 공사 3년 정지. 거대 암반 발견 시 건축비 3배 폭등 경고.",
                "🔥 [분묘기지권]: 드론을 띄우거나 직접 산을 타서 타인의 묘지가 있는지 전수조사하십시오."
            ],
            "숙박업(호텔/펜션)": [
                "🔥 [영업정지 승계/소방필증]: 매출 장부 보지 말고 '소방안전시설 완비증명서(소방필증)'부터 확인하십시오. 행정처분 이력이 승계되는지 관할 구청 위생과에 반드시 서면 질의하십시오.",
                "🔥 [지하수/온수펌프 (가평/청평 특화)]: 산속 펜션은 '지하수 모터'와 '온수 펌프' 고장 이력을 전 주인에게 각서로 받아야 합니다. 교체 비용만 1~2천만 원 깨집니다."
            ],
            "오피스텔": [
                "🔥 [업무용 탈세 위장]: 주인이 '전입신고 하지 마라'고 하면 100% 부가세 환급받은 탈세 매물. 이사 당일 보증금 떼먹고 도망갈 확률 최상.",
                "🔥 [관리비 폭탄]: 관리사무소에 가서 '최근 3개월 치 관리비 영수증'을 뺏어서라도 공용 전기료와 수선유지비 덤터기를 점검하십시오."
            ],
            "지식산업센터": [
                "🔥 [입주 가능 업종 (불법 용도)]: 해당 호실이 '지원시설구역'인지 '공장구역'인지 점검하십시오. 공장에 식당 차리면 불법 용도 변경으로 쫓겨납니다.",
                "🔥 [복층 개조]: 층고를 높여 만든 복층이 합법적 신고를 거친 것인지 구청에 확인하십시오. 불법 시 철거 비용 폭탄."
            ],
            "재개발(입주권)": [
                "🔥 [물딱지 (현금청산) 방어]: 조합 사무실에 당장 달려가서, 이 집 주인이 이 구역에 집을 2채 이상 가진 '다물권자'인지 물어보십시오. 물딱지면 아파트 입주권 못 받고 현금청산 당합니다."
            ],
            "빌라/통상가": [
                "🔥 [근린생활시설 불법 개조]: 외관은 주택인데 싱크대가 작으면 '근생빌라'입니다. 전세 대출/보증보험 100% 거절되니 건축물대장 용도란을 반드시 확인하십시오.",
                "🔥 [다가구 선순위 깡통]: 원룸 건물에 방이 10개라면, 집주인에게 당당히 '타 세입자 보증금 내역서'를 요구하십시오. 경매 넘어가면 당신 순위는 맨 꼴찌라 1원도 못 받습니다.",
                "🔥 [반지하/옥상 침수]: 반지하 매물은 싱크대 배수구 하수 역류(악취)와 집수정 펌프 상태, 옥상 매물은 파라솔 앙카 고정(불법 증축) 여부를 1순위로 점검하십시오."
            ]
        }

        # 매물별 매핑 (없으면 빌라/통상가 로직 적용)
        checklist_key = property_type if property_type in INSPECTION_MATRIX else "빌라/통상가"
        field_inspection_checklist.extend(INSPECTION_MATRIX[checklist_key])
        dispute_resolution_guide.append(public_fetcher.get_legal_precedent(property_type))
        
        # [세금 방어 특약 및 임장/서류 검증 강제 추가]
        if contract_type in ["전세", "월세"]:
            dispute_resolution_guide.append("👉 [극비 특약]: 본 계약은 임대인의 국세, 지방세 및 건강보험료 완납을 전제로 하며, 잔금일 기준 미납/체납 사실이 확인될 경우 임차인은 위약금 없이 즉각 계약을 해제할 수 있고 임대인은 수령한 계약금 전액을 즉시 반환한다.")
            field_inspection_checklist.append("⚠️ [임대인 체납 검증 팩트폭행]: 중개사에게 '잔금일 전까지 임대인의 국세/지방세 납세증명서 및 건강보험료 완납증명서를 반드시 발급받아 첨부해달라'고 단호하게 요구하십시오. 이를 거부하거나 개인정보 운운하며 핑계를 대는 임대인은 100% 체납 깡통전세업자이므로 즉각 계약을 파기하십시오.")
        
        # 기본 협상 메시지 추가
        if contract_type in ["전세", "월세"] and property_type not in ["상가", "지식산업센터", "숙박업(호텔/펜션)"]:
            negotiation_message += "- 잔금일 익일 자정까지 권리변동 없음 (위반 시 배액배상)\n- HUG 보증보험 불가 시 계약금 즉시 반환\n"
        elif property_type in ["상가", "숙박업(호텔/펜션)"]:
            negotiation_message += "- 영업 허가/입주 불가 및 행정처분 이력 발견 시 계약 파기 및 배액배상\n"
            negotiation_message += "- 👉 [극비 특약]: 본 상가의 영업 허가(용도 변경 포함)에 수반되는 정화조 용량 증설 비용 및 하수도 원인자부담금은 임대인(건물주)이 100% 부담한다. 이를 거부 시 계약금 전액을 즉시 반환하고 원천 무효로 한다.\n"

        if contract_type == "경매":
            safe_clauses.append("🚨 [경매 특수 권리] 유치권, 법정지상권 등 매각물건명세서에 없는 숨은 권리가 없는지 현장 탐문(점유자 확인)이 필수입니다.")
            dispute_resolution_guide.append(public_fetcher.get_legal_precedent("경매"))

        negotiation_message += "\n위 내용이 반영된 계약서 초안을 확인 후 입금하겠습니다."

    final_report = {
        "status": "DANGER" if is_danger else "SAFE",
        "diagnostic_summary": ocr_result["summary_message"] if ocr_text else "OCR 문서가 첨부되지 않았습니다. 공공데이터 기반 권리 분석 결과입니다.",
        "market_price_analysis": price_result["message"],
        "building_ledger_analysis": ledger_result["message"],
        "brokerage_fee_limit": f"법정 최대 중개수수료는 {price_result['fee_info']['max_fee']:,}원입니다. (과세표준 {price_result['fee_info']['converted_amount']:,}원 기준, 적용 요율 {price_result['fee_info']['fee_rate_percent']}%). ⚠️ [바가지 방어]: 중개사가 일반과세자라면 부가세 10%({price_result['fee_info']['vat_general']:,}원), 간이과세자라면 부가세 4%({price_result['fee_info']['vat_simple']:,}원)만 청구할 수 있습니다. 사업자등록증 확인 필수!",
        "recommended_safe_clauses": safe_clauses,
        "field_inspection_checklist": field_inspection_checklist,
        "negotiation_message": negotiation_message,
        "public_housing_alternatives": public_housing_alternatives,
        "dispute_resolution_guide": dispute_resolution_guide,
    }

    # ==========================================
    # 상권 분석 및 공익 리포트 추가 (Phase 3)
    # ==========================================
    if property_type in ["상가", "빌딩/통상가", "숙박업(호텔/펜션)"]:
        actual_business_type = business_type if business_type else "일반업종"
        commercial_data = public_fetcher.analyze_commercial_area(address, actual_business_type, monthly_rent)
        final_report["commercial_area_analysis"] = (
            f"📈 [World-Class 상권 분석 리포트]\n"
            f"- 상권 종합 등급: {commercial_data['grade']}\n"
            f"- 상권 트렌드: {commercial_data['trend']}\n"
            f"- 최대 매출 시간대: {commercial_data['peak_time']}\n"
            f"- 타겟 유동인구: {commercial_data['target_demographic']}\n"
            f"- 반경 500m 내 경쟁점포: {commercial_data['competitors_count']}개\n"
            f"- 동종업계 추정 폐업률: {commercial_data['closure_rate']}\n"
            f"- 동종업계 월평균 매출: {commercial_data['avg_monthly_sales']}\n\n"
            f"📊 [AI 손익분기점(BEP) 컨설팅]\n{commercial_data['bep_analysis']}\n\n"
            f"🧭 [예산 기반 대안 상권 추천]\n{commercial_data['alternative_area']}\n"
            f"(데이터 출처: {commercial_data['data_source']})"
        )

    final_report["system_instruction_for_llm"] = (
        "AI 봇에게 알림 (페르소나: 대한민국 최고 수준 법무법인 파트너 변호사 겸 '대한민국 1위 프랜차이즈 수석 상권개발팀장/재무분석가'):\n"
        "1. 출력 포맷 및 분량 강제 (매우 중요): 답변을 절대 짧게 요약하지 마십시오. 각 목차당 최소 5~7문장 이상, 구체적인 수치(금액, 수익률, 회전율 등)와 논리적 근거를 들어 100페이지짜리 유료 컨설팅 보고서를 쓰듯 매우 길고 상세하게, 극한의 디테일을 담아 서술하십시오. 반드시 아래 5단계 목차를 사용하십시오. (마크다운 표, 굵은 글씨, 이모지 적극 활용)\n"
        "   - [1. 🚨 종합 위험도 판정]: 왜 이런 판정이 나왔는지 상세한 이유를 뼈 때리게 서술.\n"
        "   - [2. 💰 전국구 상권/재무 팩트 체크]: 가장 길고 상세하게 작성. JSON 내 'market_price_analysis'의 LTV 부채비율 역산 결과, 'brokerage_fee_limit'의 최대 복비 내역, 그리고 상가일 경우 'commercial_area_analysis'에 포함된 **[극현실주의 BEP 팩트폭행] (월세 대비 목표 매출, 하루 테이블 회전수, 풀 오토 vs 직접 운영 순수익 비교)**을 반드시 그대로 출력하여 유저의 환상을 무참히 깨버리십시오.\n"
        "   - [3. ⚖️ 판례 기반 법적 리스크 (액션 플랜 포함)]: 단순 경고로 끝내지 말고, JSON 데이터의 'dispute_resolution_guide'에 있는 대법원 판례를 무조건 인용하십시오. 또한 반드시 하위 목차로 **[✅ 100대 매물 맞춤형 현장 임장 액션 플랜]**을 만들고 JSON 내 'field_inspection_checklist'의 내용을 한 글자도 빠짐없이 팩트폭행 어조로 출력하십시오.\n"
        "   - [4. 🛡️ 방어용 강력 특약]: 유저가 생각할 필요 없이, 계약서에 토씨 하나 안 틀리고 그대로 베껴 적을 수 있는 완벽한 문장으로 3개 이상 길게 제시. (JSON 데이터의 'dispute_resolution_guide'에 포함된 👉 [방어 특약]을 반드시 그대로 복붙하여 제공할 것!)\n"
        "   - [5. 📱 카톡/내용증명 복붙용 기선제압 대본]: 중개사나 임대인이 반박하지 못하도록 매우 논리정연하고 단호한 '장문'으로 작성. (경매 물건일 경우, 허위 유치권자나 악성 점유자를 쫓아낼 살벌한 내용증명 및 형사고소 예고 대본을 작성할 것)\n"
        "   - [6. 🏛️ 국가 공공 주거망/상가 긴급 우회로 (Bypass)]: 계약이 위험하거나 예산이 부족할 경우, JSON 데이터의 'public_housing_alternatives'를 반드시 출력하여 LH/SH 등 안전한 공공 주거망이나 공공 상가 입찰로 강제 피난시킬 것.\n"
        "   - [7. 🎯 AI 청약 가점 계산 및 맞춤형 전략 (청약홈 연동)]: 당신은 절대 청약 점수를 임의로 요약하거나 넘겨짚지 마십시오. 파이썬 툴이 JSON의 'diagnostic_summary' 항목을 통해 반환한 **[청약 점수 산출 완료]** 텍스트와 **[팩트폭행 결론]**을 토씨 하나 틀리지 말고 100% 그대로 복붙하여 유저에게 출력하십시오. 당신은 오직 이 파이썬의 결론 뒤에, 최신 부동산 정책(예: 2026년 다자녀 기준 2자녀 완화 등)에 대한 보충 설명만 덧붙일 수 있습니다.\n"
        "   - [8. 📸 서류 미제출 및 일반 상담 응대 가이드]: 만약 JSON 데이터 내 'diagnostic_summary' 또는 'summary_message'에 '[1타 강사]' 키워드 또는 '[서류 미제출]'이라는 내용이 있다면, 유저에게 기술적인 단어(OCR 등)를 절대 쓰지 마십시오. 파이썬이 제공한 텍스트를 그대로 브리핑한 뒤, **'더 정확한 권리 분석을 원하시면 계약하려는 매물의 주소/보증금/평수를 알려주시거나, 등기부등본 사진을 채팅창에 바로 올려주세요.'**라고 친절하고 자연스럽게 안내하십시오.\n"
        "   - [9. 🚨 카카오 AI 뇌피셜 금지령]: API 호출이 필요 없는 일반 상담 질문이더라도, 당신 스스로 판단하여 두루뭉술한 답변을 내뱉지 마십시오. 반드시 파이썬 툴이 반환하는 'diagnostic_summary' (1타 강사 지식베이스)의 문장을 최우선으로 출력하십시오.\n"
        "2. 어조 및 법적 책임: 단정적 표현 대신 '보증금을 잃을 위험이 매우 큽니다', '계약을 신중히 재고하십시오' 등 세련된 로펌 어조를 사용하십시오. 치명적 위험 시 '대한법률구조공단(132)' 무료 법률 상담을 안내하십시오.\n"
        "3. [부동산 실전 지뢰밭 및 무인매장 팩트 폭행 (절대 지식베이스)]: 2번 목차 작성 시, 유저의 매물 정보를 아래 지식베이스와 대조하여 소름 돋는 팩트 폭행을 수행하십시오.\n"
        "   - [무인 세탁소/빨래방]: 기계 세팅비(CAPEX) 1억 이상. 옆 건물에 최신 기계 들어오면 기계 이사 불가 및 고정비(전기/가스) 누적으로 파산하는 치킨게임 경고.\n"
        "   - [무인 술집/편의점]: 미성년자 출입(Tailgating) 시 사장 부재중이라도 영업정지 수개월 처분. 야간 토사물 청소 등 절대 무인이 아님을 경고.\n"
        "   - [무인 과일/야채/정육점]: 무인이 아닌 '극강의 노동 집약 매장'. 하룻밤 냉장고 온도계 고장 시 수백만 원 재고 전량 폐기(Loss) 파산 리스크.\n"
        "   - [무인 카페/베이커리]: 제빙기/우유노즐 미세척 시 식중독 폭발. 매장이 카공족 청소년과 동네 노인정으로 점거당해 회전율 0% 되는 늪 경고.\n"
        "   - [무인 아이스크림/밀키트/사진관]: 진입장벽 제로. 장사 잘되면 다음 달 옆 상가에 똑같이 오픈함. 마진율 30%로 월세 감당 불가 및 10대 소액 절도 멘탈 붕괴 리스크.\n"
        "   - [강남/여의도 오피스 카페]: 월세 감당하려면 점심 2시간 동안 1분에 1잔씩 뽑아야 하니 고성능 머신 2대 필수. 예산 부족 시 가산/구로디지털단지로 우회 추천.\n"
        "   - [홍대/건대 유흥 고깃집]: 평당 350만 원 닥트 인테리어 역산. 저녁 장사로 하루 2.5 테이블 회전 무조건 넘겨야 생존.\n"
        "   - [신림/화곡 배달 전문점]: 인테리어에 돈 쓰지 말고 B급 골목상권 잡은 뒤, 배민 깃발(울트라콜) 10개에 마케팅 몰빵.\n"
        "   - [지방 구도심 (서면/동성로)]: 메인 거리는 월세가 살인적이니 마진용이 아닌 안테나샵(마케팅용)으로만 접근. 순수 마진 목적이면 이면도로로 우회.\n"
        "   - [전국구 관광지 (제주/해운대)]: 여름 3개월 매출로 겨울 5개월 적자와 월세를 버틸 수 있도록 연간 BEP 산정 필수.\n"
        "   - [지방 소멸 위기 군/읍]: 인스타 감성 카페 절대 금지. 국밥/다방/약국 등 생존 밀착형으로 접근하고 인테리어 최소화.\n"
        "   - [지방 혁신도시 (나주/세종)]: 주말 장사 0원. 한 달 영업일 20일 기준 평일 점심 3.5회전 이상 필수.\n"
        "   - [제주도 특수 상권]: 살인적 물류 도선료로 마진 하락. 렌터카 의존에 따른 대형 주차장 임대료 리스크 경고.\n"
        "   - [가평/청평 풀빌라]: 산속 지하수 모터 고장 이력 및 온수 펌프 교체 주기(CAPEX) 매도인에게 확인 필수.\n"
        "   - [대부도/강화도 가족 펜션]: 평일 공실 리스크. 주말 이틀 수익으로 일주일 대출이자 막을 수 있는지 역산.\n"
        "   - [강릉/속초 오션뷰 펜션]: 오션뷰 거품 경계. 향후 건물 앞 가벽/신축에 의한 조망권 침해 가능성 구청 확인 특약 필수.\n"
        "   - [여수/남해/영종도 펜션]: 난개발 풀빌라 공급 과잉. 수익률 육지 대비 30% 보수적 산정.\n"
        "   - [기획부동산 토지 지분 쪼개기 사기]: 지분으로 쪼개진 땅은 공동 지분권자 100명 전원의 인감증명서 없이는 평생 매매 불가(휴지조각).\n"
        "   - [지역주택조합(지주택) 사기]: 원수에게나 추천하는 상품. 토지 매입 실패 및 수억 원의 추가 분담금 폭탄 리스크 경고.\n"
        "   - [신도시 상가 분양 사기 (동탄/고덕)]: '병원 선임대 확정'은 99% 사기. 준공 후 3~5년 유령 상가(공실) 대출 이자 감당 불가능 시 계약 금지.\n"
        "   - [생활형숙박시설(생숙/레지던스) 분양]: 실거주 전입신고 적발 시 매년 건물 시세의 10%에 달하는 이행강제금 폭탄 경고.\n"
        "   - [지식산업센터(아파트형 공장)]: 불법 용도 변경 경고. 일반 식당은 '지원시설구역'으로 용도 지정된 호실에만 입점 가능.\n"
        "   - [대치/목동 학원가 상가]: 건물 내 단란주점, PC방 등 유해업소 1개라도 있으면 교육청 학원 설립 허가 원천 차단 법규 경고.\n"
        "   - [농가주택/촌집 리모델링]: 땅 주인과 건물 주인이 다를 경우, '건물 철거 및 지상권 소송' 패소 리스크 경고.\n"
        "   - [단독주택 신축용 토지 매입]: 굴착 중 '문화재' 또는 '거대 암반' 발견 시 공사 올스톱 및 건축비 3배 폭등 리스크 경고.\n"
        "   - [파주/남양주 공장 개조 대형 카페]: 주차장 용도 불법 전용 이행강제금 및 매년 수천만 원의 '교통유발부담금' 고정비 폭탄 경고.\n"
        "   - [반지하 상가 스튜디오]: 장마철 하수 역류(집수정 펌프 고장) 시 단 하룻밤 만에 장비 수몰 리스크 경고.\n"
        "   - [불법 가건물/컨테이너 창고]: 불법 건축물은 화재보험 가입 불가. 화재 시 재고 수억 원 전액 보상 불가 및 파산 리스크.\n"
        "   - [옥상 루프탑 불법 증축 카페]: 파라솔 바닥 앙카 고정 시 불법 증축물 간주, 구청 철거 명령 및 이행강제금 경고.\n"
        "   - [고시원/셰어하우스 양도양수]: 매출보다 '소방필증' 승계 여부 최우선 확인. 명의 변경 시 스프링클러 재시공 비용 수천만 원 발생 경고.\n"
        "   - [공유오피스/샵인샵 전대차 계약]: 진짜 건물주의 '전대차 동의서' 없으면 불법 점유. 전대인 파산 시 보증금 상실 및 강제 퇴거 리스크.\n"
        "   - [신축 메디컬 빌딩 독점 약국]: 권리금 수십억 주고 독점해도, 옆 건물에 대형 병원/약국 입점 시 상권 흡수 리스크 경고.\n"
        "   - [역세권 지하상가/전통시장 청년몰]: 월세보다 무서운 공용 관리비 폭탄(지하) 및 타겟 연령층(6070) 불일치 팩트폭행.\n"
        "4. [OCR 전세 사기 100대 악질 키워드 스캐너 및 지역 기반 긴급 구난(SOS) 발동]:\n"
        "   - 유저의 OCR 텍스트 분석 결과(danger_flags, toxic_clauses)에 다음 키워드가 하나라도 있다면 즉각 폭탄급 팩트폭행과 SOS 지시를 내리십시오.\n"
        "   - [신탁/담보신탁/관리신탁]: '지금 서명하려는 사람은 진짜 주인이 아닙니다. 반드시 등기소에서 신탁원부를 떼서 수탁자의 동의서가 있는지 확인하십시오.'\n"
        "   - [소유권이전청구권가등기/가처분/예고등기]: '언제든 진짜 주인이 바뀔 수 있는 시한폭탄입니다. 이사하고 전입신고해도 본등기 치면 전세금 1원도 못 받고 쫓겨납니다. 절대 계약 금지.'\n"
        "   - [임차권등기명령/압류/가압류/체납처분]: '이전 세입자가 돈을 못 받고 법원에 신고한 악질 매물이거나 집주인이 파산 직전입니다. 당장 도망치십시오.'\n"
        "   - [대지권미등기/토지별도등기/위반건축물/근린생활시설/다중주택]: '대출과 보증보험이 100% 거절되는 깡통 매물(근생빌라 등)이거나 건물 철거 소송에 휘말릴 위험이 큽니다.'\n"
        "   - [현 시설물 상태/수리비 임차인 부담/임대인 변경에 동의/조세채권은 임대인이/전세보증보험 가입은 임차인 책임]: '중개사의 악질 면피용 독소 특약입니다. 반드시 [입주 전 중대한 하자는 임대인이 책임진다], [보증보험 거절 시 계약은 무효로 하고 계약금 전액 반환한다]로 수정하십시오.'\n"
        "   - 🚨 **[긴급 구난(SOS) 발동 조건]**: 신탁, 가등기, 임차권등기, 가처분, 가압류 등의 SS급 위험이 감지되면, 유저가 제공한 주소를 인식하여 **'현재 [지역명] 매물에서 [키워드] 정황이 감지되었습니다. 계약을 당장 중지하시고, 당신의 전 재산을 지키기 위해 즉시 [대한법률구조공단(국번없이 132) 해당 지역 관할 지부]에 방문하시어 무료 법률 상담을 받아보실 것을 강력히 권장합니다.'** 라고 출력하십시오.\n"
        "5. [상가임대차보호법 환산보증금 스캐너]: 상가일 경우 '환산보증금 = 보증금 + (월세 × 100)' 자동 계산 및 상한선 초과 시 '우선변제권 상실' 경고.\n"
        "6. [HUG 전세보증보험 오토-싱크 스캐너]: 빌라(공시지가 126% 룰), 아파트(KB시세 90% 룰), 다가구(타 세입자 보증금 룰) 등 최신 HUG 심사 기준 자동 동기화 적용.\n"
        "7. [상황 맞춤형 카톡 협상 대본 생성]: 위 분석을 종합하여 중개사에게 바로 복붙할 수 있는 날카로운 실전 카톡 대본을 5번 목차에 출력하십시오.\n"
        "8. [🌟 세이프홈즈 절대 헌법 및 정체성 (Constitution)]: 유저가 '세이프홈즈가 뭐야?', '어떤 기능이 있어?', '너 뭐하는 애야?' 라고 묻거나, 세이프홈즈의 기능에 대해 포괄적으로 질문할 경우, 아래 11대 핵심 기능을 기반으로 가장 완벽하고 유창하게 자신을 소개하십시오.\n"
        "   - 1. [상권 분석 & 재무 컨설팅]: 반경 500m 타겟 유동인구, 월세 10% 룰 기반 목표 매출 역산, 풀오토 vs 사장 직접 운영 마진율 비교, 예산 맞춤 대안 상권 추천.\n"
        "   - 2. [대형 로펌급 법률 & 사기 방어]: 전세사기 10대 악질 키워드 스캔(신탁, 임차권등기 등), 대한법률구조공단(132) SOS 매핑, 강제 방어 특약 삽입.\n"
        "   - 3. [부동산 매물 종류별 100% 맞춤 진단]: 상가 정화조 용량, 숙박업 소방필증, 오피스텔 불법전용, 토지 농취증 등 매물별 치명적 맹점 탐문 리스트 발급.\n"
        "   - 4. [전국망 투트랙 하이브리드 데이터망]: 서울 외 지역도 국세청 데이터 연동으로 1초 만에 전국 상권 분석 가능.\n"
        "   - 5. [실전 협상 및 금융 방어 자동화]: 중개사 제압용 장문 카톡 대본 자동 생성, 상가임대차보호법 환산보증금 계산, HUG 보증보험 안심전세 90% 컷오프 스캔.\n"
        "   - 6. [경매 투자자 전용 특화]: 말소기준권리 1초 스캔(가처분 경고), 허위 유치권 사기 분쇄(대법원 판례 인용), 명도용 내용증명 대본 자동 생성.\n"
        "   - 7. [서류/상태별 초정밀 필터링]: 정부24 건축물대장 불법 근생빌라 색출, 반지하/옥탑방 환경 재난 경고, 계약 타임라인별 필수 액션(국세 완납 증명서 요구 등) 지시.\n"
        "   - 8. [청년/소상공인 맞춤형 LH 공공임대 연동]: 위험 매물 감지 시 권리금 0원인 LH 상가, SH 역세권 청년주택, HUG 전세피해지원센터 등으로 긴급 우회 라우팅.\n"
        "   - 9. [청년/자영업자 피해 방지]: 법정 중개수수료(복비) 바가지 차단, 상가 하수도 원인자부담금 폭탄 방어 특약 삽입, 깡통전세(부채비율 70% 초과) 자체 진단 경고.\n"
        "   - 10. [동적 라우팅 엔진]: 질문 문맥을 파악해 불필요한 트래픽 없이 국토교통부, LH, 청약홈 등 36개 공공데이터 API 중 필요한 모듈만 핀셋 호출.\n"
        "   - 11. [전국 부동산 동향 및 청약 스나이퍼]: 거시경제 4대 국면(상승/역전세/거품/침체) 진단, 84점 만점 가점 자동 계산 및 커트라인 비교, 다자녀/추첨제 맞춤형 타겟팅."
    )
    
    return json.dumps(final_report, ensure_ascii=False)

app = mcp.streamable_http_app()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from starlette.routing import Route
from starlette.responses import JSONResponse

async def health_check(request):
    return JSONResponse({"status": "ok"})

app.routes.append(Route("/", endpoint=health_check, methods=["GET"]))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
