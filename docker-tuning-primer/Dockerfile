FROM alpine:latest

RUN apk add --no-cache --no-progress bc mysql mysql-client ncurses socat && \
    rm -rf /var/cache/apk/*

COPY root /

ENV TERM rxvt

ENTRYPOINT [ "/tuning-primer-wrapper.sh" ]
