# DSMR Smart Meter MQTT Client

Lightweight containerized Dutch Smart Meter (_Slimme Meter_) to MQTT
software, with automatic Home Assistant integration.

Uses [paho-mqtt](https://pypi.org/project/paho-mqtt/) and
[ndokter/dsmr_parser](https://github.com/ndokter/dsmr_parser) to do the
heavy lifting.

## Is this you?
You've been running Home Assistant on a Raspberry Pi in the _meterkast_
for a while. You've hooked it up directly to your Smart Meter with
a USB cable, and you're happily using the built-in [DSMR Slimme
Meter](https://www.home-assistant.io/integrations/dsmr/) integration.

But now you want to move Home Assistant to a server in the attic,
without physical access to your Smart Meter. You want to use the MQTT protocol to
let the Raspberry Pi in the _meterkast_ smoothly communicate with Home
Assistant upstairs. You want a turn-key, easy to configure, well-engineered
application for the job.

Then mqtt4dsmr is right for you!

## Usage
The examples use `podman` since I'm more familiar with it than `docker`,
but they should be relatively interchangeable.

### Trying it out
When using rootless containers, make sure your user has the right group
membership to access serial ports (this is why the `--gorup-add` option
is there). On Fedora Linux this group is called `dialout`.

```
podman run -d                                             \
    --name mqtt4dsmr                                      \
    --group-add keep-groups                               \
    --tz=local                                            \
    --env MQTT_HOST=mqtt.home.example.org                 \
    --env MQTT_PORT=1883                                  \
    --env MQTT_USERNAME=my_user                           \
    --env MQTT_PASSWORD=my_password                       \
    --device /dev/serial/by-id/usb-MY_DEVICE:/dev/ttyDSMR \
    ghcr.io/antonijn/mqtt4dsmr
```

### Automated execution
Put the following in `~/.config/containers/systemd/mqtt4dsmr.container`:

```
[Unit]
Description=De Slimme Meter MQTT Client
After=network-online.target

[Container]
ContainerName=mqtt4dsmr
Image=ghcr.io/antonijn/mqtt4dsmr:latest
Annotation=run.oci.keep_original_groups=1
Environment=MQTT_HOST=mqtt.home.example.org
Environment=MQTT_PORT=1883
Environment=MQTT_USERNAME=my_user
Environment=MQTT_PASSWORD=my_password
AddDevice=/dev/serial/by-id/usb-MY_DEVICE:/dev/ttyDSMR
Timezone=local

[Service]
Restart=always

[Install]
WantedBy=default.target
```

Use additional environment variables as required, per the documentation
below.

Enable the container using `systemctl --user start mqtt4dsmr`. To
automatically start the daemon at system start-up while using rootless
containers, enable lingering for your user: `loginctl enable-linger <my-user>`.

## Options
Options must be given to the container as environment variables.
<table>
  <tr>
    <td>Option</td>
    <td>Description</td>
    <td>Default</td>
  </tr>
  <tr>
    <td><pre>MQTT_HOST</pre></td>
    <td>IP address or URL for MQTT broker.</td>
    <td></td>
  </tr>
  <tr>
    <td><pre>MQTT_PORT</pre></td>
    <td>Broker MQTT port. If set to 8883 and <pre>MQTT_TLS</pre> is not
        explicitly defined, then <pre>MQTT_TLS</pre> defaults to <pre>true</pre> (Optional).</td>
    <td>1883</td>
  </tr>
  <tr>
    <td><pre>MQTT_USERNAME</pre></td>
    <td>MQTT username. (Optional)</td>
    <td></td>
  </tr>
  <tr>
    <td><pre>MQTT_PASSWORD</pre></td>
    <td>MQTT password. (Optional if <pre>MQTT_USERNAME</pre> is not set)</td>
    <td></td>
  </tr>
  <tr>
    <td><pre>MQTT_TLS</pre></td>
    <td>Use MQTT over TLS. If set to <pre>true</pre> and <pre>MQTT_PORT</pre> is not
        explicitly defined, then <pre>MQTT_PORT</pre> defaults to 8883. (Optional)</td>
    <td><pre>false</pre></td>
  </tr>
  <tr>
    <td><pre>MQTT_TLS_INSECURE</pre></td>
    <td>Disable hostname verification for MQTT over TLS. (Optional)</td>
    <td><pre>false</pre></td>
  </tr>
  <tr>
    <td><pre>MQTT_CA_CERTS</pre></td>
    <td>CA bundle file for broker verification. Only relevant for MQTT
        over TLS. (Optional)</td>
    <td>system CA bundle</td>
  </tr>
  <tr>
    <td><pre>MQTT_CERTFILE</pre></td>
    <td>Client certificate for authentication. (Optional)</td>
    <td></td>
  </tr>
  <tr>
    <td><pre>MQTT_KEYFILE</pre></td>
    <td>Client keyfile for authentication. (Optional)</td>
    <td></td>
  </tr>
  <tr>
    <td><pre>MQTT_TOPIC_PREFIX</pre></td>
    <td>Topic prefix for application MQTT traffic. You should probably
        not change the default values unless you know it will conflict.
        (Optional)</td>
    <td><pre>dsmr</pre></td>
  </tr>
  <tr>
    <td><pre>HA_DEVICE_ID</pre></td>
    <td>Home Assistant internal device ID. You should probably not
        change the default values unless you know it will conflict.
        (Optional)</td>
    <td><pre>dsmr</pre></td>
  </tr>
  <tr>
    <td><pre>HA_DISCOVERY_PREFIX</pre></td>
    <td>Home Assistant discovery prefix. This should match the value
        you have configured in your Home Assistant MQTT integration.
        If you have not configured such a value, then don't change this
        option. (Optional)</td>
    <td><pre>homeassistant</pre></td>
  </tr>
  <tr>
    <td><pre>DSMR_VERSION</pre></td>
    <td>Dutch Smart Meter Specification version. Can be one of
        <pre>AUSTRIA_ENERGIENETZE_STEIERMARK</pre>,
        <pre>BELGIUM_FLUVIUS</pre>, <pre>EON_HUNGARY</pre>,
        <pre>ISKRA_IE</pre>, <pre>LUXEMBOURG_SMARTY</pre>, <pre>Q3D</pre>,
        <pre>SAGEMCOM_T210_D_R</pre>, <pre>SWEDEN</pre>, <pre>V2_2</pre>,
        <pre>V3</pre>, <pre>V4</pre>, <pre>V5</pre>. See
        [ndokter/dsmr_parser](https://github.com/ndokter/dsmr_parser)
        for more information. (Optional)</td>
    <td><pre>V4</pre></td>
  </tr>
  <tr>
    <td><pre>SERIAL_SETTINGS</pre></td>
    <td>Serial settings. Is probably related to your <pre>DSMR_VERSION</pre>
        setting. Worth playing around with if things don't work
        initially. Can be one of <pre>V2_2</pre>, <pre>V4</pre>,
        <pre>V5</pre>. See [ndokter/dsmr_parser](https://github.com/ndokter/dsmr_parser)
        for more information. (Optional)</td>
    <td><pre>V4</pre></td>
  </tr>
</table>
