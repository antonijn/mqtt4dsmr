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
import re


class SensorKind:
    def __init__(self, subtopic, device_class, unit, icon, state_class):
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


class Sensor:
    def __init__(self, key, topic, kind, disambig):
        self.key = key
        self.topic = topic
        self.kind = kind
        self.disambig = disambig

    def name(self):
        name = self.key[0] + self.key[1:].lower().replace('_', ' ')

        # hacky manual replacements!
        name = name.replace('l1', 'L1')
        name = name.replace('l2', 'L2')
        name = name.replace('l3', 'L3')

        if self.disambig:
            name = name + ' ' + self.disambig

        return name

    def uid(self, dev_id):
        name = f'{dev_id}_{self.key}'
        if self.disambig:
            reg_dis = re.sub(r'[^a-zA-Z0-9_]', '', self.disambig.replace(' ', '_'))
            name = name + '_' + reg_dis
        return name.lower()


class Schema:
    def __init__(self, telegram, topic):
        self.attributes = {}
        self.add_attributes(self.attributes, telegram, topic)

        self.mbus_attributes = {}
        for mbus_dev in telegram.MBUS_DEVICES:
            channel_id = mbus_dev.channel_id
            mbus_attr = {}
            self.add_attributes(mbus_attr, mbus_dev, f'{topic}/mbus{channel_id}')
            if mbus_attr:
                self.mbus_attributes[channel_id] = mbus_attr

    # 'telegram' may also be an mbus device
    def add_attributes(self, attrs, telegram, topic):
        unit_info = {
            'W':   SensorKind('elec', 'power',   'W',   'mdi:lightning-bolt', 'measurement'),
            'kW':  SensorKind('elec', 'power',   'kW',  'mdi:lightning-bolt', 'measurement'),
            'Wh':  SensorKind('elec', 'energy',  'Wh',  'mdi:lightning-bolt', 'total'),
            'kWh': SensorKind('elec', 'energy',  'kWh', 'mdi:lightning-bolt', 'total'),
            'V':   SensorKind('elec', 'voltage', 'V',   'mdi:lightning-bolt', 'measurement'),
            'm3':  SensorKind('gas',  'gas',     'm³',  'mdi:meter-gas',      'total')
        }
        diag = SensorKind('diag', None, None, 'mdi:counter', None)

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
                logging.debug(f'{attr} NOT part of schema')
                continue

            attr_topic = kind.topic_name(topic, attr)
            logging.debug(f'{attr} will be part of schema @ {attr_topic}')
            attrs[attr] = (attr_topic, kind)

    def publish_attributes(self, attrs, client, telegram):
        for key, (topic, _) in attrs.items():
            val = getattr(telegram, key).value
            client.publish(topic, str(val))

    def publish(self, client, telegram):
        logging.debug('Sending message according to schema')

        self.publish_attributes(self.attributes, client, telegram)

        for channel_id, attrs in self.mbus_attributes.items():
            mbus_dev = telegram.get_mbus_device_by_channel(channel_id)
            self.publish_attributes(attrs, client, mbus_dev)

    def publish_ha_discovery(self, client, disc_pfx, dev_id, availability):
        all_keys = []
        for key in self.attributes.keys():
            all_keys.append(key)
        for attrs in self.mbus_attributes.values():
            for key in attrs.keys():
                all_keys.append(key)

        # Find out if we have any duplicate keys (several mbus devices
        # may use the same key, I think -- better safe than sorry).
        # We try not to disambiguate if possible, since this would
        # otherwise only clutter the human-readable name in HA.
        key_histogram = {}
        for key in all_keys:
            if key not in key_histogram:
                key_histogram[key] = 0
            key_histogram[key] += 1

        all_sensors = []
        for key, (topic, kind) in self.attributes.items():
            all_sensors.append(Sensor(key, topic, kind, None))
        for channel_id, attrs in self.mbus_attributes.items():
            for key, (topic, kind) in attrs.items():
                disamb = f'(channel {channel_id})' if key_histogram[key] > 1 else None
                all_sensors.append(Sensor(key, topic, kind, disamb))

        device = {
            'identifiers': [dev_id],
            'name': 'DSMR Smart Meter',
        }
        simple_device = {'identifiers': [dev_id]}

        for sensor in all_sensors:
            uid = sensor.uid(dev_id)
            sensor_msg = {
                'name': sensor.name(),
                'state_topic': sensor.topic,
                'unique_id': uid,
                'device': device,
                'availability_topic': availability,
            }
            sensor.kind.amend_sensor_dict(sensor_msg)

            config_topic = f'{disc_pfx}/sensor/{uid}/config'
            client.publish(config_topic, json.dumps(sensor_msg), retain=True)
            logging.debug(f'HA discovery: {sensor_msg}')

            # We only need to send the full specs once
            # see https://www.home-assistant.io/integrations/mqtt/#sensors
            device = simple_device
