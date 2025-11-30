# 使用 Python 3.11 作为基础镜像
# 如果 python:3.11-slim 拉取失败，可以尝试：
# FROM python:3.11
# 或 FROM python:3.11.0-slim
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# 复制项目文件
COPY . .

# 创建数据目录
RUN mkdir -p /data

# 设置数据目录环境变量
ENV DATA_DIR=/data

# 运行应用
CMD ["python", "main.py"]

