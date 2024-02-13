FROM python:3.12.2-alpine3.18@sha256:c9b14533a6a0016a4d2def5099bc420507f5a5cbcd783bf1ea0977eeeacd1339

WORKDIR /tmp

COPY requirements.txt .

RUN MAKEFLAGS="-j $(nproc)" pip install --no-cache-dir --require-hashes --no-deps -r requirements.txt && \
  rm -f requirements.txt

WORKDIR /opt/blacklist_init

COPY main.py .

ENTRYPOINT [ "python3", "main.py" ]
