FROM python:3.12-slim

ARG BUILD_NUMBER=0

WORKDIR /app

# No system dependencies needed — DB connectivity checked via Python

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY alembic/ alembic/
COPY app/ app/
COPY start.sh .
RUN chmod +x start.sh

ENV BUILD_NUMBER=$BUILD_NUMBER

EXPOSE 8000

CMD ["./start.sh"]
