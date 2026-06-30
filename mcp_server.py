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
    ocr_text: Annotated[str, Field(description="등기부등본 및 계약서의 전체 OCR 추출 텍스트")],
    address: Annotated[str, Field(description="진단할 부동산의 도로명 주소 또는 지번 주소")],
    deposit: Annotated[int, Field(description="계약 예정인 매매대금 또는 전/월세 보증금 (단위: 만원)")],
    contract_type: Annotated[str, Field(description="계약 종류 ('매매', '전세', '월세', '경매' 중 택1)")],
    property_type: Annotated[str, Field(description="매물 종류 ('주택', '상가', '오피스텔', '지식산업센터', '빌딩/통상가', '숙박업(호텔/펜션)', '재개발(입주권)', '토지(전/답)', '임야(산/묘지)' 중 택1)")],
    current_status: Annotated[str, Field(description="현재 진행 상태 ('계약 전', '계약 중', '사고 발생/분쟁' 중 택1)")] = "계약 전",
    monthly_rent: Annotated[int, Field(description="월세 금액 (단위: 만원)")] = 0,
    business_type: Annotated[str, Field(description="상가/지산일 경우 희망 업종")] = ""
) -> str:
    # 1. OCR 및 공공데이터 스캔
    ocr_result = ocr_parser.analyze_ocr_text(ocr_text, contract_type, property_type)
    ledger_result = public_fetcher.check_building_ledger(address, property_type, business_type)
    flood_result = public_fetcher.check_flood_risk(address)
    price_result = public_fetcher.get_market_price_risk(address, deposit, monthly_rent, contract_type, property_type)
    
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
    if is_danger and contract_type in ["전세", "월세"] and property_type in ["주택", "오피스텔"] and current_status in ["계약 전", "계약 중"]:
        public_housing_alternatives = public_fetcher.get_public_housing_notices(deposit)

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

        # 임장 체크리스트
        if property_type in ["주택", "상가", "오피스텔"]:
            if ledger_result["is_basement"]:
                field_inspection_checklist.append("반지하 매물입니다. 하수구 악취 역류 여부와 채광 상태를 점검하세요.")
            else:
                field_inspection_checklist.append("수압 체크: 싱크대와 화장실 변기 물을 동시에 틀어 수압이 떨어지는지 확인하세요.")
            if property_type == "오피스텔":
                field_inspection_checklist.append("오피스텔은 숨겨진 공용 관리비가 매우 비쌉니다. 중개사에게 '최근 3개월 치 관리비 영수증'을 반드시 요구하여 고정 지출을 파악하세요.")
            
        for toxic in ocr_result.get("toxic_clauses_found", []):
            safe_clauses.append(f"🚨 [독소조항 삭제 요망] 계약서의 '{toxic}' 관련 문구는 불리하므로 삭제를 요청하세요.")

        if contract_type == "경매":
            if ocr_result["auction_analysis"].get("has_assumed_rights"):
                safe_clauses.append(ocr_result["auction_analysis"]["warning"])

        negotiation_message = (
            f"[소장님, 계약 진행 전 몇 가지 확인 부탁드립니다.]\n"
            f"1. 등기부등본 및 신분증 진위 확인 부탁드립니다.\n"
            f"2. 계약서 특약사항에 아래 내용을 꼭 포함해 주시기 바랍니다.\n"
        )
        if contract_type in ["전세", "월세"] and property_type in ["주택", "오피스텔"]:
            negotiation_message += "- 잔금일 익일 자정까지 권리변동 없음\n- HUG 보증보험 불가(또는 전입신고 불가) 시 계약금 반환"
        elif property_type in ["상가", "지식산업센터"]:
            negotiation_message += "- 영업 허가/입주 불가 시 계약금 반환 및 정화조 부담금 임대인 부담"
        negotiation_message += "\n위 내용이 반영된 계약서 초안을 확인 후 입금하겠습니다."

    final_report = {
        "status": "DANGER" if is_danger else "SAFE",
        "diagnostic_summary": ocr_result["summary_message"],
        "brokerage_fee_limit": f"법정 최대 중개수수료는 {price_result['brokerage_fee_limit']:,}만 원입니다.",
        "recommended_safe_clauses": safe_clauses,
        "field_inspection_checklist": field_inspection_checklist,
        "negotiation_message": negotiation_message,
        "public_housing_alternatives": public_housing_alternatives,
        "dispute_resolution_guide": dispute_resolution_guide,
    }

    # ==========================================
    # 상권 분석 및 공익 리포트 추가 (Phase 3)
    # ==========================================
    if property_type in ["상가", "빌딩/통상가", "숙박업(호텔/펜션)"] and business_type:
        commercial_data = public_fetcher.analyze_commercial_area(address, business_type)
        final_report["commercial_area_analysis"] = (
            f"📊 [AI 상권 분석 (자영업자 공익 보호 시스템)]\n"
            f"- 데이터 출처: {commercial_data['data_source']}\n"
            f"- 타겟 유동인구: {commercial_data['target_demographic']}\n"
            f"- 반경 500m 내 경쟁점포: {commercial_data['competitors_count']}개\n"
            f"- 동종업계 추정 폐업률: {commercial_data['closure_rate']}\n"
            f"- 동종업계 월평균 매출: {commercial_data['avg_monthly_sales']}\n"
            f"💡 [AI 조언] 계약상 법적 위험이 없더라도, 경쟁 점포 수와 폐업률을 반드시 고려하여 신중히 창업을 결정하시기 바랍니다."
        )

    final_report["system_instruction_for_llm"] = "AI 봇에게 알림: 1. 제공된 매매가/보증금을 바탕으로 최신 부동산 정부 정책(LTV 한도, 전세대출)을 적용해 '예상 대출 가능 금액'을 계산하세요. 2. 해당 매물 종류와 매매가를 바탕으로 최신 대한민국 세법을 웹 검색 또는 최신 지식으로 확인하여, 유저가 납부해야 할 '예상 세금(취득세, 재산세, 종합부동산세 등)'을 추가로 계산하여 브리핑해 주세요. 단, '다주택자 여부 및 최신 세법 개정에 따라 실제 세금은 달라질 수 있습니다'라고 경고하세요. 3. 상권 분석 데이터(commercial_area_analysis)가 존재할 경우, 자영업자를 진심으로 걱정하고 돕는 따뜻한 컨설턴트의 톤으로 해당 매출/폐업률 데이터를 유저에게 분석해 주세요."
    
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
