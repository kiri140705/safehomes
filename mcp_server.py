import uvicorn
from fastapi import FastAPI
import json

# MCP 공식 SDK 임포트
from mcp.server.fastapi import create_mcp_server
from mcp.server import Server

from safehomes_ocr import RegistryParser
from public_data_api import PublicDataFetcher

# FastAPI 앱 및 MCP 서버 초기화
app = FastAPI(title="SafeHomes MCP Server")
mcp = Server("safehomes")

ocr_parser = RegistryParser()
public_fetcher = PublicDataFetcher()

@mcp.tool()
async def analyze_real_estate_safety(ocr_text: str, address: str, deposit: int) -> str:
    """
    등기부등본 OCR 텍스트, 주소, 보증금을 입력받아 전월세 사기 위험도(위반건축물, 깡통전세 등)를 종합 분석합니다.
    """
    # 1. OCR 텍스트 기반 등기부/계약서 분석
    ocr_result = ocr_parser.analyze_ocr_text(ocr_text)
    
    # 2. 공공데이터 기반 위반건축물 및 깡통전세 분석
    ledger_result = public_fetcher.check_building_ledger(address)
    price_result = public_fetcher.get_market_price_risk(address, deposit)
    
    # 종합 리포트 생성
    is_totally_safe = ocr_result["is_safe"] and not ledger_result["is_illegal_building"] and not price_result["is_kangtong_risk"]
    
    final_report = {
        "status": "SAFE" if is_totally_safe else "DANGER",
        "ocr_analysis": ocr_result,
        "building_ledger": ledger_result,
        "price_risk": price_result,
        "disclaimer": "※ 본 분석 결과는 공공데이터 및 통상적인 안전 기준에 따른 참고용 1차 스크리닝이며, 최종 계약에 대한 법적 책임은 지지 않습니다. 계약 전 반드시 전문가(공인중개사/변호사)와 교차 검증하시기 바랍니다."
    }
    
    return json.dumps(final_report, ensure_ascii=False)

# FastAPI 앱에 MCP 서버를 마운트하여 /mcp 경로(SSE 통신)를 열어줍니다.
mcp_app = create_mcp_server(mcp)
app.mount("/mcp", mcp_app)

# 카카오클라우드 로드밸런서(헬스체크)용 기본 엔드포인트
@app.get("/")
def health_check():
    return {"status": "ok", "message": "SafeHomes MCP Server is running."}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
