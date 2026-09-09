FROM python:3.10-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jre-headless curl procps \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 --shell /bin/bash jovyan

COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt

RUN mkdir -p /opt/spark-conf /home/jovyan/work \
    && chown -R jovyan:jovyan /opt/spark-conf /home/jovyan
COPY --chown=jovyan:jovyan config/spark-defaults.conf /opt/spark-conf/spark-defaults.conf

ENV SPARK_CONF_DIR=/opt/spark-conf
USER jovyan
WORKDIR /home/jovyan/work
CMD ["sh", "-c", "exec jupyter lab --ip=0.0.0.0 --no-browser --ServerApp.token=\"$JUPYTER_TOKEN\" --ServerApp.allow_remote_access=True"]
