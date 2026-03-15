FROM python:3.11-slim
  RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev && \
      pip install --no-cache-dir 'vectordb-bench[qdrant]' && \
      apt-get purge -y gcc libc6-dev && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
  COPY qdrant_local.py /usr/local/lib/python3.11/site-packages/vectordb_bench/backend/clients/qdrant_local/qdrant_local.py
  RUN find /usr/local/lib/python3.11/site-packages/vectordb_bench/backend/clients/qdrant_local/ -name "*.pyc" -delete
  WORKDIR /bench
  VOLUME /bench/results
  ENTRYPOINT ["sleep", "infinity"]
