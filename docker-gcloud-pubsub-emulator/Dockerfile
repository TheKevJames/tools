FROM golang:alpine as builder

RUN apk update && \
    apk upgrade && \
    apk add --update curl git

RUN curl -s https://raw.githubusercontent.com/eficode/wait-for/master/wait-for -o /usr/bin/wait-for
RUN chmod +x /usr/bin/wait-for

COPY ./pubsubc /src
WORKDIR /src
RUN go build


FROM alpine:latest

ARG TARGETPLATFORM

COPY --from=builder /usr/bin/wait-for /usr/bin
COPY --from=builder /src/pubsubc /usr/bin
COPY run.sh /run.sh

RUN apk add --no-cache --update \
        netcat-openbsd \
        openjdk8-jre \ 
        curl \
        python3=~3.9
RUN mkdir gcloud
WORKDIR /gcloud
RUN case ${TARGETPLATFORM} in \
         "linux/amd64")  gcloud_arch=x86_64  ;; \
         "linux/arm64")  gcloud_arch=ARM  ;; \
    esac \
    && curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-sdk-378.0.0-linux-${gcloud_arch}.tar.gz \
    && tar -xf google-cloud-sdk-378.0.0-linux-${gcloud_arch}.tar.gz

ENV PATH $PATH:/gcloud/google-cloud-sdk/bin
WORKDIR /
RUN gcloud components install beta pubsub-emulator --quiet

EXPOSE 8681

CMD /run.sh
