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

import json
import logging
import os
import re
import sys
import dsmr_parser.clients
from enum import Enum
from dsmr_parser import telegram_specifications
from dsmr_parser.clients import SerialReader
import paho.mqtt.client as mqtt
from config import Config

class SensorKind:
    def __init__(self, subtopic, device_class, unit, icon, state_class=None):
        self.subtopic = subtopic
        self.device_class = device_class
        self.unit = unit
        self.icon = icon
        self.state_class = state_class

    def topic_name(self, pfx, attr_name):
        return f'{pfx}/{self.subtopic}/{attr_name.lower()}'

    def amend_sensor_dict(self, sensor):
        if self.device_class is not None:
            sensor['device_class'] = self.device_class
        if self.icon is not None:
            sensor['icon'] = self.icon
        if self.unit is not None:
            sensor['unit_of_measurement'] = self.unit
        if self.state_class is not None:
            sensor['state_class'] = self.state_class

def attr_name(attr):
    name = attr[0] + attr[1:].lower().replace('_', ' ')

    # hacky manual replacements!
    name = name.replace('l1', 'L1')
    name = name.replace('l2', 'L2')
    name = name.replace('l3', 'L3')

    return name

class Schema:
    def __init__(self, telegram, topic):
        unit_info = {
            'W':   SensorKind('elec', 'power',   'W',   'mdi:lightning-bolt', state_class='measurement'),
            'kW':  SensorKind('elec', 'power',   'kW',  'mdi:lightning-bolt', state_class='measurement'),
            'Wh':  SensorKind('elec', 'energy',  'Wh',  'mdi:lightning-bolt', state_class='total'),
            'kWh': SensorKind('elec', 'energy',  'kWh', 'mdi:lightning-bolt', state_class='total'),
            'V':   SensorKind('elec', 'voltage', 'V',   'mdi:lightning-bolt', state_class='measurement'),
            'm3':  SensorKind('gas',  'gas',     'm³',  'mdi:meter-gas',      state_class='total')
        }

        diag = SensorKind('diag', None, None, 'mdi:counter')

        self.attributes = {}
        for attr, obj in telegram:
            if hasattr(obj, 'unit') and obj.unit in unit_info:
                # Values with a unit are predictable and definitely
                # useful
                kind = unit_info[obj.unit]
            elif attr.endswith('_COUNT') or attr == 'ELECTRICITY_ACTIVE_TARIFF':
                # These values seem broadly useful and predictable;
                # let's include them! The manual inclusion of the active
                # tariff is kind of janky, of course, but if it works it
                # works.
                kind = diag
            else:
                continue

            logging.debug(f'{attr} will be part of schema')
            self.attributes[attr] = (kind.topic_name(topic, attr), kind)

    def publish(self, client, telegram):
        for key, (topic, _) in self.attributes.items():
            val = getattr(telegram, key).value
            client.publish(topic, str(val))

    def publish_ha_discovery(self, client, disc_pfx, dev_id, availability):
        disc_pfx = f'{disc_pfx}/sensor'

        device = {
            'identifiers': [dev_id],
            'name': 'DSMR Smart Meter',
        }
        simple_device = {'identifiers': [dev_id]}

        for key, (topic, info) in self.attributes.items():
            uid = f'{dev_id}_{key.lower()}'
            sensor = {
                'name': attr_name(key),
                'state_topic': topic,
                'unique_id': uid,
                'device': device,
                'availability_topic': availability,
            }
            info.amend_sensor_dict(sensor)

            config_topic = f'{disc_pfx}/{uid}/config'
            client.publish(config_topic, json.dumps(sensor), retain=True)

            # We only need to send the full specs once
            # see https://www.home-assistant.io/integrations/mqtt/#sensors
            device = simple_device

def main():
    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

    cfg = Config()

    client = mqtt.Client()

    if cfg.MQTT_TLS:
        logging.info('Using MQTT over TLS')
        client.tls_set(
            ca_certs=cfg.MQTT_CA_CERTS,
            certfile=cfg.MQTT_CERTFILE,
            keyfile=cfg.MQTT_KEYFILE
        )
        client.tls_insecure_set(cfg.MQTT_TLS_INSECURE)
    else:
        logging.warning('Not using MQTT over TLS; set MQTT_PORT=8883 or set MQTT_TLS=1 to enable TLS')

    if cfg.MQTT_USERNAME:
        logging.info('Using MQTT username/password authentication')
        client.username_pw_set(cfg.MQTT_USERNAME, cfg.MQTT_PASSWORD)
    else:
        logging.info('No MQTT username/password provided')

    avail = f'{cfg.MQTT_TOPIC_PREFIX}/status'

    logging.info(f'Connecting to {cfg.MQTT_HOST}:{cfg.MQTT_PORT}')
    logging.info(f'Availibility topic: {avail}')
    client.will_set(avail, 'offline', retain=True)
    client.connect(cfg.MQTT_HOST, cfg.MQTT_PORT)
    client.loop_start()

    client.publish(avail, 'online', retain=True)

    serial_reader = SerialReader(
        device=cfg.SERIAL_PORT,
        serial_settings=cfg.SERIAL_SETTINGS,
        telegram_specification=cfg.DSMR_VERSION
    )

    schema = None
    for telegram in serial_reader.read():
        if schema is None:
            schema = Schema(telegram, cfg.MQTT_TOPIC_PREFIX)
            schema.publish_ha_discovery(client, cfg.HA_DISCOVERY_PREFIX, cfg.HA_DEVICE_ID, avail)

        schema.publish(client, telegram)

if __name__ == '__main__':
    rc = 0
    try:
        main()
    except Exception as e:
        logging.exception(e)
        rc = 1
    sys.exit(rc)
