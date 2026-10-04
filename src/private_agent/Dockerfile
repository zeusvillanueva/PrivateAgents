FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OTEL_SDK_DISABLED=true

WORKDIR /app
COPY pyproject.toml main.py ./
RUN pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 agent

ENV HOME=/home/agent
USER 10001:10001
EXPOSE 8088
CMD ["python", "main.py"]
