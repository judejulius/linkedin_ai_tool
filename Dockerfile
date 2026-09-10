FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/app/data
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY scheduler.py linkedin_auth.py dashboard.py ./
COPY frontend ./frontend
COPY examples ./examples
COPY LICENSE ./LICENSE
RUN mkdir -p /app/data
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--timeout", "300", "dashboard:create_app()"]
