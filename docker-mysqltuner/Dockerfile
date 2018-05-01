FROM alpine:latest

RUN apk --update add mysql-client perl && \
    rm -rf /var/cache/apk/*

COPY root /

ENTRYPOINT [ "/mysqltuner.pl" ]
