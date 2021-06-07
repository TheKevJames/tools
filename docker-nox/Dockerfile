FROM ubuntu:20.04

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/GMT
# https://devguide.python.org/#status-of-python-branches
RUN apt-get update -qy && \
    apt-get install -qy ca-certificates curl gnupg2 && \
    . /etc/os-release && \
    echo "deb http://ppa.launchpad.net/deadsnakes/ppa/ubuntu ${UBUNTU_CODENAME} main" > /etc/apt/sources.list.d/deadsnakes.list && \
    apt-key adv --keyserver keyserver.ubuntu.com --recv-keys F23C5A6CF475977595C89F51BA6932366A755776 && \
    apt-get update -qy && \
    apt-get install -qy \
        python2.7 \
        python2.7-dev \
        python3.5 \
        python3.5-dev \
        python3.6 \
        python3.6-dev \
        python3.7 \
        python3.7-dev \
        python3.8 \
        python3.8-dev \
        python3.9 \
        python3.9-dev \
        python3.9-distutils \
        python3-pip && \
    curl https://bootstrap.pypa.io/pip/2.7/get-pip.py --output /tmp/get-pip.py && \
    python2.7 /tmp/get-pip.py && \
    rm /tmp/get-pip.py && \
    python2.7 -m pip install --upgrade pip && \
    python3.5 -m pip install --upgrade pip && \
    python3.6 -m pip install --upgrade pip && \
    python3.7 -m pip install --upgrade pip && \
    python3.8 -m pip install --upgrade pip && \
    python3.9 -m pip install --upgrade pip && \
    python3 -m pip install 'nox==2021.6.6' && \
    rm -rf /var/cache/apt/lists
