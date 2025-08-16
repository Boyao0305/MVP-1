# ✅ 使用 Python 官方 Debian 基础镜像（基于 Debian 11 Bullseye）
FROM python:3.9-slim-bullseye

# ✅ 设置非交互模式（防止 tzdata 卡住）
ENV DEBIAN_FRONTEND=noninteractive

# ✅ 更换 apt 源为清华大学镜像（HTTP 版，避免证书问题）
RUN echo "deb http://mirrors.tuna.tsinghua.edu.cn/debian bullseye main contrib non-free\n\
deb http://mirrors.tuna.tsinghua.edu.cn/debian bullseye-updates main contrib non-free\n\
deb http://mirrors.tuna.tsinghua.edu.cn/debian-security bullseye-security main contrib non-free" \
> /etc/apt/sources.list && apt-get update

# ✅ 安装 GCC 和 G++ 编译工具
RUN apt-get install -y --no-install-recommends gcc g++

# ✅ 安装构建工具
RUN apt-get install -y --no-install-recommends make build-essential

# ✅ 安装数学库（BLAS, LAPACK）
RUN apt-get install -y --no-install-recommends libblas-dev liblapack-dev

# ✅ 安装指定版本的 libatlas3-base 和 libatlas-base-dev
RUN apt-get install -y --no-install-recommends \
    libatlas3-base=3.10.3-10 libatlas-base-dev

# ✅ 安装 Python 开发库和其他依赖
RUN apt-get install -y --no-install-recommends python3-dev espeak libespeak1 ffmpeg

# ✅ 清理 APT 缓存，减小镜像体积
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# ✅ 设置清华 pip 源，加速安装 Python 包
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 设置工作目录
WORKDIR /app

# ✅ 拷贝并安装 Python 依赖
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# ✅ 安装 spaCy 模型（如果使用的是在线模式）
# RUN python -m spacy download en_core_web_sm

# ✅ 如果使用离线模式，拷贝 spaCy 模型并安装
COPY en_core_web_sm-3.8.0-py3-none-any.whl .
RUN pip install en_core_web_sm-3.8.0-py3-none-any.whl

# ✅ 拷贝应用源码到容器中
COPY website/ website/
COPY . .

# 开放端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "300"]