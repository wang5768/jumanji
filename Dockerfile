FROM nvcr.io/nvidia/tensorflow:21.06-tf2-py3

RUN apt-get update -q \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    curl \
    git \
    libcusolver10 \
    libgl1-mesa-dev \
    libgl1-mesa-glx \
    libglew-dev \
    libosmesa6-dev \
    software-properties-common \
    net-tools \
    vim \
    virtualenv \
    wget \
    xpra \
    xvfb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade --quiet pip setuptools

COPY ./requirements.txt /tmp/requirements.txt
COPY ./requirements-dev.txt /tmp/requirements-dev.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements-dev.txt && rm -rf /tmp/*

# working directory
WORKDIR /home/app/jumanji
ENV PYTHONPATH=$PWD:$PYTHONPATH

# Tensorflow
ENV TF_FORCE_GPU_ALLOW_GROWTH=true
ENV CUDA_DEVICE_ORDER=PCI_BUS_ID
ENV TF_CPP_MIN_LOG_LEVEL=3
COPY . /home/app/jumanji

RUN pip install -e .
EXPOSE 6006
ENTRYPOINT bash

RUN DEBIAN_FRONTEND=noninteractive add-apt-repository --yes ppa:deadsnakes/ppa && apt-get update

RUN curl -o /usr/local/bin/patchelf https://s3-us-west-2.amazonaws.com/openai-sci-artifacts/manual-builds/patchelf_0.9_amd64.elf \
    && chmod +x /usr/local/bin/patchelf

ENV LANG C.UTF-8

RUN mkdir -p /root/.mujoco \
    && wget https://mujoco.org/download/mujoco210-linux-x86_64.tar.gz -O mujoco.tar.gz \
    && tar -xf mujoco.tar.gz -C /root/.mujoco \
    && rm mujoco.tar.gz

ENV LD_LIBRARY_PATH /root/.mujoco/mujoco210/bin:${LD_LIBRARY_PATH}
ENV LD_LIBRARY_PATH /usr/local/nvidia/lib64:${LD_LIBRARY_PATH}

RUN pip install git+https://github.com/openai/mujoco-py
