from fastapi import FastAPI, Request
from pydantic import BaseModel
import uvicorn
from safehomes_ocr import RegistryParser
from public_data_api import PublicDataFetcher

app = FastAPI(title="SafeHomes MCP Server")

ocr_parser = RegistryParser()
public_fetcher = PublicDataFetcher()

class AnalyzeRequest(BaseModel):
    ocr_text: str
    address: str
    deposit: int

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/analyze")
def analyze_real_estate(req: AnalyzeRequest):
    # 1. OCR 텍스트 기반 등기부/계약서 분석
    ocr_result = ocr_parser.analyze_ocr_text(req.ocr_text)
    
    # 2. 공공데이터 기반 위반건축물 및 깡통전세 분석
    ledger_result = public_fetcher.check_building_ledger(req.address)
    price_result = public_fetcher.get_market_price_risk(req.address, req.deposit)
    
    # 종합 리포트 생성
    is_totally_safe = ocr_result["is_safe"] and not ledger_result["is_illegal_building"] and not price_result["is_kangtong_risk"]
    
    final_report = {
        "status": "SAFE" if is_totally_safe else "DANGER",
        "ocr_analysis": ocr_result,
        "building_ledger": ledger_result,
        "price_risk": price_result,
        "disclaimer": "※ 본 분석 결과는 공공데이터 및 통상적인 안전 기준에 따른 참고용 1차 스크리닝이며, 최종 계약에 대한 법적 책임은 지지 않습니다. 계약 전 반드시 전문가(공인중개사/변호사)와 교차 검증하시기 바랍니다."
    }
    
    return final_report

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
