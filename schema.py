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
            'W':   SensorKind('elec', 'power',   'W',   'mdi:lightning-bolt', 'measurement'),
            'kW':  SensorKind('elec', 'power',   'kW',  'mdi:lightning-bolt', 'measurement'),
            'Wh':  SensorKind('elec', 'energy',  'Wh',  'mdi:lightning-bolt', 'total'),
            'kWh': SensorKind('elec', 'energy',  'kWh', 'mdi:lightning-bolt', 'total'),
            'V':   SensorKind('elec', 'voltage', 'V',   'mdi:lightning-bolt', 'measurement'),
            'm3':  SensorKind('gas',  'gas',     'm³',  'mdi:meter-gas',      'total')
        }

        diag = SensorKind('diag', None, None, 'mdi:counter', None)

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
        logging.debug('Sending message according to schema')
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
