# Use official Miniconda image
FROM continuumio/miniconda3

# Set working directory
WORKDIR /app

# 1️⃣ Copy environment file and create conda environment
COPY environment.yml .

# Install conda environment
RUN conda env create -f environment.yml

# 2️⃣ Activate environment and install pip-only packages
# Use full path to conda's Python for reliability in Docker
RUN /opt/conda/envs/fastapi-env/bin/pip install -i https://pypi.tuna.tsinghua.edu.cn/simple cefrpy


# 3️⃣ Update PATH and set up environment activation
ENV PATH="/opt/conda/envs/fastapi-env/bin:$PATH"
# Optional: makes "source activate" work in interactive sessions
RUN echo "source activate fastapi-env" >> ~/.bashrc

# 4️⃣ Copy spaCy model and install it
COPY en_core_web_sm-3.8.0-py3-none-any.whl .

# Install build tools (for compiling Python wheels like blis)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    build-essential \
    libblas-dev \
    liblapack-dev \
    libatlas-base-dev \
    python3-dev \
    espeak \
    libespeak1 \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Use conda env's pip explicitly to avoid issues
RUN /opt/conda/envs/fastapi-env/bin/pip install spacy \
    && /opt/conda/envs/fastapi-env/bin/pip install en_core_web_sm-3.8.0-py3-none-any.whl

# 5️⃣ Copy app source code
COPY website/ website/
COPY . .

# 6️⃣ Expose port and define startup command
EXPOSE 8000

# Use full conda env Python to run uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "300"]
# Alternative that explicitly uses conda env:
# CMD ["conda", "run", "--no-capture-output", "-n", "fastapi-env", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
