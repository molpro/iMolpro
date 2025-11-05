FROM continuumio/miniconda3:latest
RUN apt update
COPY requirements.txt /root
RUN conda install -y -c conda-forge --file=/root/requirements.txt pytest-qt 
RUN apt-get update && apt-get install libgl1-mesa-glx  -y ruby binutils librpmbuild9 rpm
RUN gem install fpm
