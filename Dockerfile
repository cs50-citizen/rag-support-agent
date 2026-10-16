# ==========================================
# Enterprise RAG Knowledge Base - Dockerfile
# ==========================================
FROM python:3.12-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# 安装系统级编译依赖 (PostgreSQL client, gcc 等)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖清单并安装
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 暴露 FastAPI 服务端口
EXPOSE 8000

# 默认启动命令 (可通过 docker-compose 覆盖以启动 celery worker)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

