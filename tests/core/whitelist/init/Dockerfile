FROM python:3.12.2-alpine3.19@sha256:25a82f6f8b720a6a257d58e478a0a5517448006e010c85273f4d9c706819478c

WORKDIR /tmp

COPY requirements.txt .

RUN MAKEFLAGS="-j $(nproc)" pip install --no-cache-dir --require-hashes --no-deps -r requirements.txt && \
  rm -f requirements.txt

WORKDIR /opt/blacklist_init

COPY main.py .

ENTRYPOINT [ "python3", "main.py" ]
