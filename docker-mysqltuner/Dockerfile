FROM alpine:latest

RUN apk --update add mysql-client perl perl-doc && \
    rm -rf /var/cache/apk/*

COPY root /

ENTRYPOINT [ "/usr/bin/perl", "/mysqltuner.pl" ]
