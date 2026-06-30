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
    description="Analyzes real estate safety risks using OCR text from contracts and property registry for SafeHomes(세이프홈즈).",
    annotations={
        "title": "SafeHomes(세이프홈즈) 부동산 위험 진단",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
def analyze_real_estate_safety(
    ocr_text: Annotated[str, Field(description="등기부등본 및 계약서의 전체 OCR 추출 텍스트")],
    address: Annotated[str, Field(description="진단할 부동산의 도로명 주소 또는 지번 주소")],
    deposit: Annotated[int, Field(description="계약 예정인 전세 또는 월세 보증금 금액 (단위: 만원)")]
) -> str:
    ocr_result = ocr_parser.analyze_ocr_text(ocr_text)
    ledger_result = public_fetcher.check_building_ledger(address)
    price_result = public_fetcher.get_market_price_risk(address, deposit)
    
    is_totally_safe = ocr_result["is_safe"] and not ledger_result["is_illegal_building"] and not price_result["is_kangtong_risk"]
    
    final_report = {
        "status": "SAFE" if is_totally_safe else "DANGER",
        "ocr_analysis": ocr_result,
        "building_ledger": ledger_result,
        "price_risk": price_result,
        "disclaimer": "본 안전 분석 결과는 공공데이터 및 예상치에 따른 참고용 1차 스크리닝이며, 최종 계약에 대한 법적 책임을 지지 않습니다. 계약 전 반드시 전문가(공인중개사, 변호사)와 교차 검증하시기 바랍니다."
    }
    
    # FastMCP automatically wraps returned strings in TextContent
    return json.dumps(final_report, ensure_ascii=False)

# Create the Streamable HTTP ASGI app
# This returns a Starlette app that listens on /mcp (default)
app = mcp.streamable_http_app()

# Add CORS Middleware to the Starlette app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add health check endpoint for KakaoCloud Liveness/Readiness probes
from starlette.routing import Route
from starlette.responses import JSONResponse

async def health_check(request):
    return JSONResponse({"status": "ok"})

app.routes.append(Route("/", endpoint=health_check, methods=["GET"]))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
