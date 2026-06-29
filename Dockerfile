FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# FastAPI 포트 노출 (PlayMCP가 접근할 포트)
EXPOSE 8000

# 서버 실행
CMD ["uvicorn", "mcp_server:app", "--host", "0.0.0.0", "--port", "8000"]
