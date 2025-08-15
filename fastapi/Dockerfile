# ✅ 使用 Python 官方 Debian 基础镜像
FROM python:3.9-slim

# ✅ 设置非交互模式（防止 tzdata 卡住）
ENV DEBIAN_FRONTEND=noninteractive

# ✅ 更换 apt 源为阿里云，加速系统依赖安装
# ✅ 覆盖 apt 源为阿里云（HTTP 版，避免证书问题）
RUN echo "deb http://mirrors.aliyun.com/debian bullseye main contrib non-free\n\
deb http://mirrors.aliyun.com/debian bullseye-updates main contrib non-free\n\
deb http://mirrors.aliyun.com/debian-security bullseye-security main contrib non-free" \
> /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc g++ make build-essential \
        libblas-dev liblapack-dev libatlas-base-dev \
        python3-dev espeak libespeak1 ffmpeg && \
    apt-get clean && rm -rf /var/lib/apt/lists/*


# ✅ 设置清华 pip 源，加速安装
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 设置工作目录
WORKDIR /app

# ✅ 拷贝 requirements.txt 并安装
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# ✅ 拷贝 spaCy 模型（如果你用的是离线 .whl 文件）
COPY en_core_web_sm-3.8.0-py3-none-any.whl .
RUN pip install en_core_web_sm-3.8.0-py3-none-any.whl

# ✅ 拷贝应用源码
COPY website/ website/
COPY . .

# 开放端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "300"]
