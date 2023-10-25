FROM python:3.11.6-alpine3.18@sha256:527e0b0d92686a3ab1af3e65fdef12a47a9359f298dfd9b8d36617808d4029e9

WORKDIR /tmp

COPY requirements.txt .

RUN MAKEFLAGS="-j $(nproc)" pip install --no-cache-dir --require-hashes -r requirements.txt && \
  rm -f requirements.txt

WORKDIR /opt/blacklist_init

COPY main.py .

ENTRYPOINT [ "python3", "main.py" ]
