FROM alpine:latest

MAINTAINER Kevin James <kevinjames@thekev.in>

RUN apk add --update bash bc mysql mysql-client ncurses socat && \
    rm -rf /var/cache/apk/*

COPY root /

ENV TERM rxvt

ENTRYPOINT [ "/tuning-primer-wrapper.sh" ]
