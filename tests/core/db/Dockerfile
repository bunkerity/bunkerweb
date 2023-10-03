FROM python:3.11.5-alpine@sha256:cd311c6a0164f34a7edbf364e05258b07d66d3f7bc155139dcb9bef88a186ded

WORKDIR /tmp

COPY requirements.txt .

RUN apk add --no-cache gcc musl-dev libffi-dev && \
  MAKEFLAGS="-j $(nproc)" pip install --no-cache-dir --require-hashes -r requirements.txt && \
  rm -f requirements.txt

WORKDIR /opt/tests

RUN addgroup -g 101 nginx && \
  adduser -h /opt/tests -g nginx -s /bin/sh -G nginx -D -H -u 101 nginx

COPY --chown=nginx:nginx main.py .
ADD ./init/plugins external
ADD ./init/bunkerweb bunkerweb

RUN chown -R nginx:nginx external bunkerweb && \
  chmod -R 777 external bunkerweb

USER nginx:nginx

ENTRYPOINT [ "python3", "main.py" ]
