FROM python:3.11.18-slim@sha256:064f01707f2fc8b06bae86bb43875266c6e41bac7994e77ec5dc623c4a4d0545
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
# build-essential : nécessaire si une roue précompilée manque (ARM notamment)
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ .
COPY server_config.py .
RUN python -m grpc_tools.protoc --proto_path=grpc --python_out=. --grpc_python_out=. grpc/amkj_service.proto
CMD ["python", "-u", "main.py"]
