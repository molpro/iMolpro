FROM ubuntu
RUN apt update
RUN apt install -y python-is-python3 python3-pip wget
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh && bash  Miniconda3-latest-Linux-x86_64.sh -b
ENV PATH=/root/miniconda3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
RUN conda config --set solver libmamba
COPY  . /root/iMolpro
RUN conda install -y -c conda-forge --file=/root/iMolpro/requirements.txt
RUN conda install -y -c conda-forge pytest-qt git
RUN apt-get update && apt-get install libgl1-mesa-glx  -y
RUN conda init bash

