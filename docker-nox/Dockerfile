FROM ubuntu:18.04

# https://devguide.python.org/#status-of-python-branches
RUN apt-get update && \
    apt-get install -qy ca-certificates curl gnupg2 && \
    . /etc/os-release && \
    echo "deb http://ppa.launchpad.net/deadsnakes/ppa/ubuntu ${UBUNTU_CODENAME} main" > /etc/apt/sources.list.d/deadsnakes.list && \
    apt-key adv --keyserver keyserver.ubuntu.com --recv-keys F23C5A6CF475977595C89F51BA6932366A755776 && \
    apt-get update && \
    apt-get install -qy \
        python2.7 \
        python2.7-dev \
        python-pip \
        python3.5 \
        python3.5-dev \
        python3.6 \
        python3.6-dev \
        python3.7 \
        python3.7-dev \
        python3-pip && \
    python3 -m pip install --upgrade pip && \
    python3 -m pip install 'nox==2019.5.30' && \
    rm -rf /var/cache/apt/lists
