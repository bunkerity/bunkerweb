FROM alpine

RUN apk add py3-pip bash build-base python3-dev libffi-dev
COPY ui/requirements.txt /tmp
RUN pip3 install -r /tmp/requirements.txt

COPY gen/ /opt/bunkerized-nginx/gen
COPY confs/site/ /opt/bunkerized-nginx/confs/site
COPY confs/global/ /opt/bunkerized-nginx/confs/global
COPY ui/ /opt/bunkerized-nginx/ui
COPY settings.json /opt/bunkerized-nginx

COPY ui/prepare.sh /tmp
RUN chmod +x /tmp/prepare.sh && \
    /tmp/prepare.sh && \
    rm -f /tmp/prepare.sh

EXPOSE 5000

WORKDIR /opt/bunkerized-nginx/ui
USER nginx:nginx
ENTRYPOINT ["/usr/bin/gunicorn", "--bind", "0.0.0.0:5000", "-m", "007", "wsgi:app"]
