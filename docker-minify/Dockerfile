FROM golang:1.16.5-alpine

# TODO: versioning?
RUN apk add --no-cache --no-progress ca-certificates git && \
    go get github.com/tdewolff/minify/cmd/minify && \
    apk del --no-cache --no-progress ca-certificates git && \
    rm -rf /var/cache/apk/*
