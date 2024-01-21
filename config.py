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
import re
import dsmr_parser.clients
from dsmr_parser import telegram_specifications
from dsmr_parser.clients.settings import serial

def get_env_opt(name, ty, required, default = None):
    if name in os.environ:
        value = os.environ[name]
    else:
        if required:
            raise LookupError(f"{name} not set in environment")
        return default

    if type(ty) != type:
        # Must be a collection of permissible values
        if value not in ty:
            values = ", ".join(str(t) for t in ty)
            raise ValueError(f"{name} must be one of {values}")
        return value

    if ty == bool:
        if value.lower() in ('true', 'yes', 'y', '1'):
            return True
        if value.lower() in ('false', 'no', 'n', '0', ''):
            return False
        raise ValueError(f"{name} must be boolean")

    return ty(value)

class Config:
    def __init__(self):
        serial_settings_pfx = 'SERIAL_SETTINGS_'
        serial_settings_options = [s[len(serial_settings_pfx):] for s in dir(dsmr_parser.clients) if s.startswith(serial_settings_pfx)]
        logging.debug(f'Possible values for SERIAL_SETTINGS: {serial_settings_options}')
        serial_settings = get_env_opt('SERIAL_SETTINGS', serial_settings_options, False, 'V4')

        dsmr_vname = re.compile(r'^[A-Z0-9_]*$')
        dsmr_versions = [v for v in dir(telegram_specifications) if dsmr_vname.match(v)]
        dsmr_versions.remove('ALL')
        logging.debug(f'Possible values for DSMR_VERSION: {dsmr_versions}')
        dsmr_version = get_env_opt('DSMR_VERSION', dsmr_versions, False, 'V4')

        self.SERIAL_SETTINGS = getattr(dsmr_parser.clients, serial_settings_pfx + serial_settings)
        self.SERIAL_PORT = get_env_opt('SERIAL_PORT', str, False, '/dev/ttyDSMR')
        self.DSMR_VERSION = getattr(telegram_specifications, dsmr_version)

        self.MQTT_HOST = get_env_opt("MQTT_HOST", str, True)
        # We set it to 'None' initially; it will get its proper value once
        # we know if the user has specified port 8883
        self.MQTT_TLS = get_env_opt("MQTT_TLS", bool, False, None)
        self.MQTT_TLS_INSECURE = get_env_opt("MQTT_TLS_INSECURE", bool, False, False)
        self.MQTT_CA_CERTS = get_env_opt("MQTT_CA_CERTS", str, False)
        self.MQTT_CERTFILE = get_env_opt("MQTT_CERTFILE", str, False)
        self.MQTT_KEYFILE  = get_env_opt("MQTT_KEYFILE",  str, False)
        # Same logic as MQTT_TLS; None initially
        self.MQTT_PORT = get_env_opt("MQTT_PORT", int, False, None)
        self.MQTT_USERNAME = get_env_opt("MQTT_USERNAME", str, False)
        self.MQTT_PASSWORD = get_env_opt("MQTT_PASSWORD", str, self.MQTT_USERNAME is not None)
        self.MQTT_TOPIC_PREFIX = get_env_opt("MQTT_TOPIC_PREFIX", str, False, "dsmr")

        self.HA_DEVICE_ID = get_env_opt("HA_DEVICE_ID", str, False, 'dsmr')
        self.HA_DISCOVERY_PREFIX = get_env_opt("HA_DISCOVERY_PREFIX", str, False, "homeassistant")

        # Make sure MQTT_PORT has a valid value
        if self.MQTT_PORT is None:
            if self.MQTT_TLS is not None and self.MQTT_TLS:
                self.MQTT_PORT = 8883
            else:
                self.MQTT_PORT = 1883

        # Make sure MQTT_TLS has a valid value
        if self.MQTT_TLS is None:
            self.MQTT_TLS = self.MQTT_PORT == 8883
