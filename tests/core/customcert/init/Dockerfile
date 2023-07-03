FROM alpine

RUN apk add --no-cache bash openssl

WORKDIR /opt/init

COPY entrypoint.sh .

RUN chmod +x entrypoint.sh

ENTRYPOINT [ "./entrypoint.sh" ]