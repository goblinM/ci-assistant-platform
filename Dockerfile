FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-runtime.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements-runtime.txt

COPY pyproject.toml README.md ./
COPY ci_assistant ./ci_assistant
COPY ci_analysis_demo ./ci_analysis_demo
RUN pip install --no-cache-dir --no-deps .

COPY . .

RUN groupadd --system ci-assistant \
    && useradd --system --gid ci-assistant --home-dir /app ci-assistant \
    && mkdir -p /var/lib/ci-assistant/knowledge \
    && chown -R ci-assistant:ci-assistant /app /var/lib/ci-assistant

USER ci-assistant

EXPOSE 8080

CMD ["uvicorn", "ci_assistant.main:app", "--host", "0.0.0.0", "--port", "8080"]
