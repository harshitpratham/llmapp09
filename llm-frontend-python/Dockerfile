FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
ENV API_URL=http://llm-python:8080/api/chat
ENV PORT=5000
EXPOSE 5000
CMD ["python", "app.py"]
