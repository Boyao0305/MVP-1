FROM continuumio/miniconda3:latest

WORKDIR /app

# 复制环境文件
COPY environment.yml .

# 创建conda环境
RUN conda env create -f environment.yml

# 激活环境的快捷方式
RUN echo "source activate fastapi-env" > ~/.bashrc
ENV PATH /opt/conda/envs/fastapi-env/bin:$PATH

# 复制应用代码
COPY app.py .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
#CMD ["conda", "run", "--no-capture-output", "-n", "fastapi-env", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
