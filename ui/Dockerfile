FROM alpine

COPY ui/dependencies.sh /tmp
RUN chmod +x /tmp/dependencies.sh && \
    /tmp/dependencies.sh && \
    rm -f /tmp/dependencies.sh

COPY gen/ /opt/gen
COPY confs/site/ /opt/confs/site
COPY confs/global/ /opt/confs/global
COPY ui/ /opt/entrypoint
COPY settings.json /opt

COPY ui/prepare.sh /tmp
RUN chmod +x /tmp/prepare.sh && \
    /tmp/prepare.sh && \
    rm -f /tmp/prepare.sh

EXPOSE 5000

WORKDIR /opt/entrypoint
ENV FLASK_APP entrypoint.py
ENTRYPOINT ["/usr/bin/python3", "-m", "flask", "run", "--host=0.0.0.0"]
