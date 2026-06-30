import uvicorn
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
import json
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import Tool, TextContent
from safehomes_ocr import RegistryParser
from public_data_api import PublicDataFetcher
from fastapi.middleware.cors import CORSMiddleware
from starlette.routing import Route, Mount
from starlette.applications import Starlette

app_mcp = Server("safehomes")
ocr_parser = RegistryParser()
public_fetcher = PublicDataFetcher()

@app_mcp.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="AnalyzeRealEstateSafety",
            description="Analyzes real estate safety risks using OCR text from contracts and property registry for SafeHomes(세이프홈즈).",
            inputSchema={
                "type": "object",
                "properties": {
                    "ocr_text": {
                        "type": "string",
                        "description": "등기부등본 및 계약서의 전체 OCR 추출 텍스트"
                    },
                    "address": {
                        "type": "string",
                        "description": "진단할 부동산의 도로명 주소 또는 지번 주소"
                    },
                    "deposit": {
                        "type": "integer",
                        "description": "계약 예정인 전세 또는 월세 보증금 금액 (단위: 만원)"
                    }
                },
                "required": ["ocr_text", "address", "deposit"]
            },
            annotations={
                "title": "SafeHomes(세이프홈즈) 부동산 위험 진단",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True
            }
        )
    ]

@app_mcp.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    if name != "AnalyzeRealEstateSafety":
        raise ValueError(f"Unknown tool: {name}")
    ocr_text = arguments.get("ocr_text", "")
    address = arguments.get("address", "")
    deposit = arguments.get("deposit", 0)
    
    ocr_result = ocr_parser.analyze_ocr_text(ocr_text)
    ledger_result = public_fetcher.check_building_ledger(address)
    price_result = public_fetcher.get_market_price_risk(address, deposit)
    
    is_totally_safe = ocr_result["is_safe"] and not ledger_result["is_illegal_building"] and not price_result["is_kangtong_risk"]
    
    final_report = {
        "status": "SAFE" if is_totally_safe else "DANGER",
        "ocr_analysis": ocr_result,
        "building_ledger": ledger_result,
        "price_risk": price_result,
        "disclaimer": "본 안전 분석 결과는 공공데이터 및 예상치에 따른 참고용 1차 스크리닝이며, 최종 계약에 대한 법적 책임은 지지 않습니다. 계약 전 반드시 전문가(공인중개사, 변호사)와 교차 검증하시기 바랍니다."
    }
    
    return [TextContent(type="text", text=json.dumps(final_report, ensure_ascii=False))]

# SSE Transport
sse = SseServerTransport(
    "/mcp/messages/",
    security_settings=TransportSecuritySettings(enable_dns_rebinding_protection=False)
)

async def handle_sse(scope, receive, send):
    async with sse.connect_sse(scope, receive, send) as streams:
        await app_mcp.run(streams[0], streams[1], app_mcp.create_initialization_options())

app = FastAPI(title="SafeHomes MCP Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    return {"status": "ok"}

from fastapi import Request

@app.get("/mcp")
@app.get("/mcp/sse")
async def sse_endpoint(request: Request):
    from starlette.responses import Response
    await handle_sse(request.scope, request.receive, request._send)
    return Response()

app.mount("/mcp/messages", sse.handle_post_message)
app.mount("/messages", sse.handle_post_message)
app.mount("/mcp/mcp/messages", sse.handle_post_message)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
