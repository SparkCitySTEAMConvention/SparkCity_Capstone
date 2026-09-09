# jupyter.Dockerfile
# Custom Jupyter image with PySpark and required dependencies

FROM jupyter/pyspark-notebook:spark-3.4.0

USER root

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    vim \
    git \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

USER $NB_UID

# Install Python packages
COPY requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt

# Install additional Jupyter extensions
RUN pip install \
    jupyterlab-git \
    jupyter-resource-usage \
    ipywidgets

# Spark JVM options
ENV SPARK_OPTS="--driver-java-options=-Xms2g --driver-java-options=-Xmx4g"

WORKDIR /home/jovyan/work