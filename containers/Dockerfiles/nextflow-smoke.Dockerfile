FROM public.ecr.aws/docker/library/python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-21-jre-headless \
    curl \
    libgomp1 \
  && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    pydantic==2.10.6 \
    pydantic-settings==2.7.1 \
    structlog==24.4.0 \
    prometheus-client==0.21.0 \
    pyyaml==6.0.1 \
    requests==2.31.0 \
    dnachisel==3.2.16 \
    celery==5.3.6 \
    viennarna>=2.6.4 \
    joblib==1.3.2 \
    scikit-learn==1.4.1.post1 \
    jsonschema==4.26.0 \
    numpy==1.26.4 \
    pandas>=2.0

ENV PYTHONPATH=/workspace

RUN curl -s https://get.nextflow.io | bash && \
    mv nextflow /usr/local/bin/ && \
    chmod +x /usr/local/bin/nextflow && \
    nextflow -version

WORKDIR /workspace

COPY services ./services
COPY agent ./agent
COPY pipelines/nextflow ./pipelines/nextflow
COPY pipelines/nextflow/smoke_test/main.nf ./main.nf

CMD ["nextflow", "run", "main.nf"]
