FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./

# The tmpfs mount is a workaround
# https://github.com/rust-lang/cargo/issues/8719
RUN --mount=type=tmpfs,target=/root/.cargo \
    apt-get update \
 && apt-get install --yes --no-install-recommends \
        build-essential libssl-dev libffi-dev cargo pkg-config \
 && pip install --no-cache-dir -r requirements.txt \
 && apt-get autoremove --purge --yes \
        build-essential libssl-dev libffi-dev cargo pkg-config \
 && apt-get clean \
 && rm -rf /root/.cache

COPY . .
ARG VERSION_TAG=unknown
ENV MQTT4DSMR_VERSION=$VERSION_TAG
CMD [ "env", "SERIAL_DEVICE=/dev/ttyDSMR", "./mqtt4dsmr.py" ]
