FROM python:3.12.1-alpine3.18@sha256:fb759579d60cfe1f70b110a27be95aaa7cf758d2fa21cf54fffb71c2ba3f8034

WORKDIR /tmp

COPY requirements.txt .

RUN MAKEFLAGS="-j $(nproc)" pip install --no-cache-dir --require-hashes --no-deps -r requirements.txt && \
  rm -f requirements.txt

WORKDIR /opt/tests

COPY main.py .

RUN apk add --no-cache curl

ENTRYPOINT [ "python3", "main.py" ]
