FROM python:3.11-slim
WORKDIR /app
RUN pip install fastapi uvicorn pydantic --no-cache-dir
COPY serve.py .
EXPOSE 8080
CMD ["uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8080"]