FROM python:3-alpine
WORKDIR /opt/mqtt4dsmr
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .
ARG VERSION_TAG=unknown
ENV MQTT4DSMR_VERSION=$VERSION_TAG
CMD [ "env", "SERIAL_DEVICE=/dev/ttyDSMR", "./mqtt4dsmr.py" ]
