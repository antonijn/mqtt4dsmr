#!/usr/bin/env python3
#
# Copyright (c) 2024, Antonie Blom
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

import logging
import os
import sys
from dsmr_parser.clients import SerialReader, SocketReader
import paho.mqtt.client as mqtt
from config import Config
from schema import Schema
from rate_limit import DirectPublisher, RateLimitedPublisher


def on_connect(client, userdata, flags, rc, properties):
    if rc == 0:
        logging.info('Connected to broker')
        client.publish(avail, 'online', retain=True)
    else:
        logging.error('Broker connection failed')


def on_disconnect(client, userdata, disconnect_flags, rc, properties):
    logging.error('Disconnected from broker')


def main():
    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)
    version = os.getenv('MQTT4DSMR_VERSION', 'unknown')
    logging.info(f'Using mqtt4dsmr {version}')

    cfg = Config()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id=cfg.MQTT_CLIENT_ID)

    if cfg.MQTT_TLS:
        logging.info('Using MQTT over TLS')
        client.tls_set(
            ca_certs=cfg.MQTT_CA_CERTS,
            certfile=cfg.MQTT_CERTFILE,
            keyfile=cfg.MQTT_KEYFILE
        )
        client.tls_insecure_set(cfg.MQTT_TLS_INSECURE)
    else:
        logging.warning('Not using MQTT over TLS; set MQTT_PORT=8883 or MQTT_TLS=1 to enable TLS')

    if cfg.MQTT_USERNAME:
        logging.info('Using MQTT username/password authentication')
        client.username_pw_set(cfg.MQTT_USERNAME, cfg.MQTT_PASSWORD)
    else:
        logging.info('No MQTT username/password provided')

    global avail
    avail = f'{cfg.MQTT_TOPIC_PREFIX}/status'

    logging.info(f'Connecting to {cfg.MQTT_HOST}:{cfg.MQTT_PORT}')
    logging.info(f'Availibility topic: {avail}')
    client.will_set(avail, 'offline', retain=True)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.connect(cfg.MQTT_HOST, cfg.MQTT_PORT)
    client.loop_start()

    if cfg.DSMR_INTERFACE == 'tcp':
        device_reader = SocketReader(
            host=cfg.DSMR_TCP_HOST,
            port=cfg.DSMR_TCP_PORT,
            telegram_specification=cfg.DSMR_VERSION
        )
    else:
        device_reader = SerialReader(
            device=cfg.SERIAL_DEVICE,
            serial_settings=cfg.SERIAL_SETTINGS,
            telegram_specification=cfg.DSMR_VERSION
        )

    publisher = None
    for telegram in device_reader.read():
        logging.debug('Received serial message')

        if publisher is None:
            schema = Schema(telegram, cfg.MQTT_TOPIC_PREFIX)
            if cfg.HA_DEVICE_ID != '':
                schema.publish_ha_discovery(
                    client, cfg.HA_DISCOVERY_PREFIX, cfg.HA_DEVICE_ID, avail)

            if cfg.MESSAGE_INTERVAL > 0:
                publisher = RateLimitedPublisher(schema, client, cfg.MESSAGE_INTERVAL)
            else:
                publisher = DirectPublisher(schema, client)

        publisher.publish(telegram)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logging.exception(e)
    sys.exit(1)
