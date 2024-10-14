#FROM ubuntu
FROM continuumio/miniconda3:latest
RUN apt update
# RUN apt install -y python-is-python3 python3-pip  wget
# RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh && bash  Miniconda3-latest-Linux-x86_64.sh -b
# ENV PATH=/root/miniconda3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
#RUN conda config --set solver libmamba
#COPY  . /root/iMolpro
COPY requirements.txt /root
RUN conda install --solver=classic conda-forge::conda-libmamba-solver conda-forge::libmamba conda-forge::libmambapy conda-forge::libarchive
RUN conda install -y -c conda-forge --file=/root/requirements.txt pytest-qt git python=3.12 scipy=1.11
RUN conda remove -y pubchempy
RUN pip install -I https://github.com/molpro/PubChemPy/archive/refs/heads/master.zip
RUN apt-get update && apt-get install libgl1-mesa-glx  -y ruby binutils librpmbuild9 rpm
RUN gem install fpm
#RUN conda init bash
#RUN conda config --add channels defaults
#RUN  conda install -n base libarchive -c main --force-reinstall
