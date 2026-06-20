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

CMD ["interview-prep-mcp"]
