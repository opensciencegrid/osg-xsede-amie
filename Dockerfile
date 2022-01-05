FROM ubuntu:18.04

RUN export DEBIAN_FRONTEND=noninteractive DEBCONF_NONINTERACTIVE_SEEN=true && \
    apt update && apt install -y --no-install-recommends \
        python3 \
        python3-dev \
        python3-pip \
        vim \
    && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install amieclient simplejson elasticsearch-dsl

# copy our app
WORKDIR /opt/apps/osg-xsede
COPY . . 

# run the app
CMD ["python3", "/opt/apps/osg-xsede/lib/Main.py"]

