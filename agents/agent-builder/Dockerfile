FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --pre -r requirements.txt
COPY shared ./shared
COPY agents/agent-builder ./agents/agent-builder
ENV PYTHONPATH=/app
EXPOSE 8088
CMD ["python", "agents/agent-builder/main.py"]
