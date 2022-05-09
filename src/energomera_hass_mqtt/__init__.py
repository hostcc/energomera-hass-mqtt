# Copyright (c) 2022 Ilia Sotnikov
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
Package to read data from Energomera energy meter and send over to
HomeAssistant using MQTT.
"""

import json

from iec62056_21.messages import CommandMessage
from iec62056_21.client import Iec6205621Client
from iec62056_21 import utils
from asyncio_mqtt import Client as mqtt_client


class EnergomeraHassMqtt:
    """
    Communicates with Energomera energy meters using IEC 62056-21 (supersedes
    IEC 61107) and sends values of requested parameters to HomeAssisstant using
    MQTT.

    :param port: Serial port the meter is connected to
    :param password: Password to enter programming session with the meter
    :param mqtt_host: Hostname or IP addres of MQTT broker
    :param mqtt_user: User to authenticate to MQTT broker with
    :param mqtt_password: Password for the user above
    :param mqtt_tls_context: SSL/TLS context to use while connecting to
     MQTT broker, necessary if it uses SSL/TLS
    :param hass_discovery_prefix: MQTT topic prefix for HomeAssistant
     discovery
    """

    @staticmethod
    def calculate_bcc(bytes_data: bytes):
        """
        Calculates protocol BCC using Energomera non-standard modification of
        IEC 1155-78.

        See http://www.energomera.ru/documentations/product/ce301_303_rp.pdf,
        page 126, for more details.

        :param bytes_data: The data to calculate BCC over
        :return: Calculated BCC
        """
        bcc = 0
        for elem in bytes_data:
            bcc += elem
            bcc = bcc & 0xFF
        bcc = bcc & 0x7F
        return bcc.to_bytes(length=1, byteorder='big')

    def __init__(
        self, port, password,
        mqtt_host, mqtt_user, mqtt_password, mqtt_tls_context=None,
        hass_discovery_prefix='homeassistant'
    ):
        # Override the method in the `iec62056_21` library with the specific
        # implementation
        # pylint: disable=protected-access
        utils._calculate_bcc = EnergomeraHassMqtt.calculate_bcc

        self._client = Iec6205621Client.with_serial_transport(
            port=port, password=password
        )
        self._hass_discovery_prefix = hass_discovery_prefix
        self._model = None
        self._serial_number = None
        self._sw_version = None
        self._mqtt_host = mqtt_host
        self._mqtt_user = mqtt_user
        self._mqtt_password = mqtt_password
        self._mqtt_tls_context = mqtt_tls_context
        self._hass_config_entities_published = {}
        # Parameters to read from the meter, and their representation to
        # HomeAssistant
        self._parameters = [
            dict(address='ET0PE', name='Cumulative energy',
                 device_class='energy', state_class='total_increasing',
                 unit='kWh', response_idx=0),
            dict(address='ECMPE', name='Monthly energy', device_class='energy',
                 state_class='total', unit='kWh', response_idx=0),
            dict(address='ECDPE', name='Daily energy', device_class='energy',
                 state_class='total', unit='kWh', response_idx=0),
            dict(address='POWPP', name=[
                 'Active energy, phase A',
                 'Active energy, phase B',
                 'Active energy, phase C'],
                 device_class='power',
                 state_class='measurement', unit='kW'),
            dict(address='POWEP', name='Active energy', device_class='power',
                 state_class='measurement', unit='kW'),
            dict(address='VOLTA', name=[
                 'Voltage, phase A',
                 'Voltage, phase B',
                 'Voltage, phase C'],
                 device_class='voltage', state_class='measurement',
                 unit='V'),
            dict(address='VNULL', name='Neutral voltage',
                 device_class='voltage', state_class='measurement', unit='V'),
            dict(address='CURRE', name=[
                 'Current, phase A',
                 'Current, phase B',
                 'Current, phase C'],
                 device_class='current',
                 state_class='measurement', unit='A'),
            dict(address='FREQU', name='Frequency', device_class='frequency',
                 state_class='measurement', unit='Hz'),
        ]

    def iec_read_values(self, address, additional_data=None):
        """
        Reads value(s) at selected address from the meter using IEC 62056-21
        protocol.

        :param address: Address of meter parameter to read
        :param additional_data: Additional data to read the parameter with
         (argument to parameter's address)
        :return: Parameter's data received from the meter
        """

        request = CommandMessage.for_single_read(
            address, additional_data
        )
        self._client.transport.send(request.to_bytes())

        return self._client.read_response().data

    async def iec_to_hass_payload(
        self, address, name, device_class, state_class, unit, response_idx=None
    ):
        """
        Reads selected parameters using IEC 62056-21 protocol from the meter
        and sends them over to HomeAssistant using MQTT.

        :param address: Address of meter parameter to read
        :param name: Name of the HomeAssistant sensor corresponds to the
         parameter
        :param device_class: Device class of the HomeAssistant sensor to send
         the parameter for
        :param state_class: Class of the sensor state in HomeAssistant
        :param unit: Unit of measure for the sensor state
        :param response_idx: Whether to pick specific entry from multi-value
         parameter, zero-based
        """
        resp = self.iec_read_values(address)
        if response_idx is not None:
            resp = [resp[response_idx]]

        if isinstance(name, list):
            # Make a copy to retain original content, is needed because `name`
            # is modified if multiple values of the same address are requested
            name = name[:]

        for idx, item in enumerate(resp):
            item_name = name
            hass_device_id = f'{self._model}_{self._serial_number}'
            hass_unique_id = f'{hass_device_id}_{item.address}'

            # Multiple addresses with likely same name, the caller has to
            # provide meaningful names for those anyways even if they are
            # different by a reason
            if len(resp) > 1:
                hass_unique_id += f'_{idx}'
                # Pick next name if a list has been provided
                if isinstance(name, list):
                    item_name = name.pop(0)
                # Otherwise append the item index to make name unique
                else:
                    item_name += f'_{idx}'

            # Compose base element of MQTT topics
            topic_base_parts = [
                'sensor', hass_device_id, hass_unique_id,
            ]
            if self._hass_discovery_prefix:
                topic_base_parts.insert(0, self._hass_discovery_prefix)
            topic_base = '/'.join(topic_base_parts)

            # Config and state MQTT topics for HomeAssistant discovery, see
            # https://www.home-assistant.io/docs/mqtt/discovery/ for details
            config_topic = f'{topic_base}/config'
            state_topic = f'{topic_base}/state'
            # Config payload for sensor discovery
            config_payload = dict(
                name=item_name,
                device=dict(
                    name=self._serial_number,
                    ids=hass_device_id,
                    model=self._model,
                    sw_version=self._sw_version,
                ),
                device_class=device_class,
                unique_id=hass_unique_id,
                unit_of_measurement=unit,
                state_class=state_class,
                state_topic=state_topic,
                value_template='{{ value_json.value }}',
            )
            json_config_payload = json.dumps(config_payload)
            # Sensor state payload
            state_payload = dict(
                value=item.value
            )
            json_state_payload = json.dumps(state_payload)

            # Send payloads using MQTT
            async with mqtt_client(
                hostname=self._mqtt_host,
                username=self._mqtt_user, password=self._mqtt_password,
                tls_context=self._mqtt_tls_context,
            ) as client:
                # Send config payload for HomeAssitant discovery only once per
                # sensor
                if (hass_unique_id not in
                        self._hass_config_entities_published):
                    await client.publish(
                        config_topic,
                        payload=json_config_payload,
                        retain=True,
                    )
                    self._hass_config_entities_published[hass_unique_id] = True

                # Send sensor state payload
                await client.publish(
                    state_topic,
                    payload=json_state_payload,
                )

    async def iec_read_admin(self):
        """
        Primary method to loop over the parameters requested and process them.
        """
        self._client.connect()

        self._client.startup()
        # Start the session in programming mode since it is faster one, as it
        # switches to baud rate higher than initial (300 baud, as per IEC
        # 62056-21, mode C). Requires password to be provided when constructing
        # the instance of the class
        self._client.ack_with_option_select("programming")
        self._client.read_response()
        self._client.send_password()
        self._client.read_response()

        # Read meter identification (mode, SW version, serial number)
        iec_hello_resp = self.iec_read_values('HELLO')[0]
        [_, self._model, self._sw_version, self._serial_number, _
         ] = iec_hello_resp.value.split(',')

        # Process parameters requested
        for param in self._parameters:
            await self.iec_to_hass_payload(
                address=param['address'], name=param['name'],
                device_class=param['device_class'],
                state_class=param['state_class'],
                unit=param['unit'],
                response_idx=param.get('response_idx', None),
            )
        # End the session
        self._client.send_break()
        self._client.disconnect()
