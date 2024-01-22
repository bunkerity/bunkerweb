FROM python:3.12.1-alpine3.18@sha256:28b825667534d432c2ec234b334de5f829624698adfa6a3fef38c4fe165922d0

WORKDIR /tmp

COPY requirements.txt .

RUN MAKEFLAGS="-j $(nproc)" pip install --no-cache-dir --require-hashes --no-deps -r requirements.txt && \
  rm -f requirements.txt

WORKDIR /opt/tests

COPY main.py .

RUN apk add --no-cache curl

ENTRYPOINT [ "python3", "main.py" ]
