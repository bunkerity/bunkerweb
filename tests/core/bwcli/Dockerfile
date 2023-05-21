FROM python:3.11.3-alpine

WORKDIR /tmp

COPY requirements.txt .

RUN MAKEFLAGS="-j $(nproc)" pip install --no-cache -r requirements.txt && \
  rm -f requirements.txt

WORKDIR /opt/tests

COPY main.py .

ENTRYPOINT [ "python3", "main.py" ]
