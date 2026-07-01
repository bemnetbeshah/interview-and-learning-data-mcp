FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV INTERVIEW_PREP_DB_PATH=/data/interview_prep.sqlite3
ENV MCP_TRANSPORT=streamable-http
ENV MCP_HOST=0.0.0.0

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import os, urllib.request; port=os.environ.get('PORT', os.environ.get('MCP_PORT', '8000')); urllib.request.urlopen(f'http://127.0.0.1:{port}/healthz', timeout=3).read()"

CMD ["interview-prep-mcp"]
