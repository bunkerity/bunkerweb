FROM python:3.11.5-alpine

WORKDIR /tmp

COPY requirements.txt .

RUN MAKEFLAGS="-j $(nproc)" pip install --no-cache -r requirements.txt && \
  rm -f requirements.txt

WORKDIR /opt/tests

COPY main.py .

RUN apk add --no-cache curl

ENTRYPOINT [ "python3", "main.py" ]