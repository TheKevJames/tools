FROM ubuntu:20.04

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/GMT
COPY requirements.txt /
# https://devguide.python.org/#status-of-python-branches
# hadolint ignore=DL3008,DL3013,SC1091
RUN apt-get update -qy && \
    apt-get install -qy --no-install-recommends \
        ca-certificates \
        curl \
        gnupg2 && \
    . /etc/os-release && \
    echo "deb http://ppa.launchpad.net/deadsnakes/ppa/ubuntu ${UBUNTU_CODENAME} main" > /etc/apt/sources.list.d/deadsnakes.list && \
    apt-key adv --keyserver keyserver.ubuntu.com --recv-keys F23C5A6CF475977595C89F51BA6932366A755776 && \
    apt-get update -qy && \
    apt-get install -qy --no-install-recommends \
        git \
        openssh-client \
        python2.7 \
        python2.7-dev \
        python3.5 \
        python3.5-dev \
        python3.6 \
        python3.6-dev \
        python3.6-distutils \
        python3.7 \
        python3.7-dev \
        python3.7-distutils \
        python3.8 \
        python3.8-dev \
        python3.8-distutils \
        python3.9 \
        python3.9-dev \
        python3.10 \
        python3.10-dev \
        python3.11 \
        python3.11-dev \
        python3.12 \
        python3.12-dev \
        python3.13 \
        python3.13-dev && \
    curl -fsSo /tmp/get-pip-2.7.py https://bootstrap.pypa.io/pip/2.7/get-pip.py && \
    curl -fsSo /tmp/get-pip-3.5.py https://bootstrap.pypa.io/pip/3.5/get-pip.py && \
    curl -fsSo /tmp/get-pip-3.6.py https://bootstrap.pypa.io/pip/3.6/get-pip.py && \
    curl -fsSo /tmp/get-pip-3.7.py https://bootstrap.pypa.io/pip/3.7/get-pip.py && \
    curl -fsSo /tmp/get-pip.py https://bootstrap.pypa.io/get-pip.py && \
    python2.7 /tmp/get-pip-2.7.py && \
    python2.7 -m pip install --no-cache-dir --upgrade pip && \
    python3.5 /tmp/get-pip-3.5.py && \
    python3.5 -m pip install --no-cache-dir --upgrade pip && \
    python3.6 /tmp/get-pip-3.6.py && \
    python3.6 -m pip install --no-cache-dir --upgrade pip && \
    python3.7 /tmp/get-pip-3.7.py && \
    python3.7 -m pip install --no-cache-dir --upgrade pip && \
    python3.8 /tmp/get-pip.py && \
    python3.8 -m pip install --no-cache-dir --upgrade pip && \
    python3.9 /tmp/get-pip.py && \
    python3.9 -m pip install --no-cache-dir --upgrade pip && \
    python3.10 /tmp/get-pip.py && \
    python3.10 -m pip install --no-cache-dir --upgrade pip && \
    python3.11 /tmp/get-pip.py && \
    python3.11 -m pip install --no-cache-dir --upgrade pip && \
    python3.12 /tmp/get-pip.py && \
    python3.12 -m pip install --no-cache-dir --upgrade pip && \
    python3.13 /tmp/get-pip.py && \
    python3.13 -m pip install --no-cache-dir --upgrade pip && \
    rm /tmp/get-pip-2.7.py && \
    rm /tmp/get-pip-3.5.py && \
    rm /tmp/get-pip-3.6.py && \
    rm /tmp/get-pip-3.7.py && \
    rm /tmp/get-pip.py && \
    python3 -m pip install --no-cache-dir -r /requirements.txt && \
    rm -rf /var/cache/apt/lists
