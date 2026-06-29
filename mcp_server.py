import uvicorn
from fastapi import FastAPI
import json

from mcp.server.fastmcp import FastMCP
from safehomes_ocr import RegistryParser
from public_data_api import PublicDataFetcher

# FastMCP 서버 초기화 (Kakao PlayMCP 규격)
mcp = FastMCP("safehomes")

ocr_parser = RegistryParser()
public_fetcher = PublicDataFetcher()

# Kakao PlayMCP 규격에 맞춰 어노테이션(annotations) 필수 입력
@mcp.tool(
    annotations={
        "title": "세이프홈즈 부동산 위험 진단",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def analyze_real_estate_safety(ocr_text: str, address: str, deposit: int) -> str:
    """
    세이프홈즈(SafeHomes) 전월세 안전 진단 비서입니다. 등기부등본 및 계약서의 OCR 텍스트와 보증금을 기반으로 공공데이터를 조회하여 위험을 분석합니다.
    """
    ocr_result = ocr_parser.analyze_ocr_text(ocr_text)
    ledger_result = public_fetcher.check_building_ledger(address)
    price_result = public_fetcher.get_market_price_risk(address, deposit)
    
    is_totally_safe = ocr_result["is_safe"] and not ledger_result["is_illegal_building"] and not price_result["is_kangtong_risk"]
    
    final_report = {
        "status": "SAFE" if is_totally_safe else "DANGER",
        "ocr_analysis": ocr_result,
        "building_ledger": ledger_result,
        "price_risk": price_result,
        "disclaimer": "※ 본 분석 결과는 공공데이터 및 통상적인 안전 기준에 따른 참고용 1차 스크리닝이며, 최종 계약에 대한 법적 책임은 지지 않습니다. 계약 전 반드시 전문가(공인중개사/변호사)와 교차 검증하시기 바랍니다."
    }
    
    return json.dumps(final_report, ensure_ascii=False)

# 메인 FastAPI 앱 설정
app = FastAPI(title="SafeHomes MCP Server")

# 카카오클라우드 로드밸런서(헬스체크)용 기본 엔드포인트
@app.get("/")
def health_check():
    return {"status": "ok", "message": "SafeHomes MCP Server is running."}

# FastMCP의 SSE 앱을 /mcp 경로에 마운트
app.mount("/mcp", mcp.sse_app())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
