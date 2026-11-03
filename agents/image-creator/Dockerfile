FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --pre -r requirements.txt
COPY shared ./shared
COPY agents/image-creator ./agents/image-creator
ENV PYTHONPATH=/app
EXPOSE 8088
CMD ["python", "agents/image-creator/main.py"]
