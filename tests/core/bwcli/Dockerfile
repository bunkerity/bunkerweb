FROM python:3.12.4-alpine3.19@sha256:ef3397d09070efd36583e83d2619cf8006158641e5b6b629d4d92a9778f5aa1c

WORKDIR /tmp

COPY requirements.txt .

RUN MAKEFLAGS="-j $(nproc)" pip install --no-cache-dir --require-hashes --no-deps -r requirements.txt && \
  rm -f requirements.txt

WORKDIR /opt/tests

COPY main.py .

ENTRYPOINT [ "python3", "main.py" ]
