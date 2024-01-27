FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ARG VERSION_TAG=unknown
ENV MQTT4DSMR_VERSION=$VERSION_TAG
CMD [ "env", "SERIAL_DEVICE=/dev/ttyDSMR", "./mqtt4dsmr.py" ]
