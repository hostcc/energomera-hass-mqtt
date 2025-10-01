# Copyright (c) 2023 Ilia Sotnikov
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

'''
Tests for handling HomeAssistant configuration payloads.
'''
import json
from unittest.mock import call
import pytest
from conftest import (
    CONFIG_YAML_BASE, MockMqttT, MockSerialT, SERIAL_EXCHANGE_BASE
)
from energomera_hass_mqtt.main import main

serial_exchange = SERIAL_EXCHANGE_BASE + [
    {
        'receive_bytes': b'\x01R1\x02ET0PE()\x037',
        'send_bytes':
            b'\x02ET0PE(0.0)\r\n'
            b'ET0PE(0.0)\r\n'
            b'ET0PE(0.0)\r\n'
            b'ET0PE(0.0)\r\n'
            b'ET0PE(0.0)\r\n'
            b'ET0PE(0.0)\r\n\x03\x04',
    },
    {
        'receive_bytes': b'\x01R1\x02ET0PE()\x037',
        'send_bytes':
            b'\x02ET0PE(0.0)\r\n'
            b'ET0PE(0.0)\r\n'
            b'ET0PE(0.0)\r\n'
            b'ET0PE(0.0)\r\n'
            b'ET0PE(0.0)\r\n'
            b'ET0PE(0.0)\r\n\x03\x04',
    },
]

CONFIG_YAML = CONFIG_YAML_BASE + '''
    parameters:
        - address: ET0PE
          device_class: energy
          name: Cumulative energy (updated)
          response_idx: 0
          state_class: total_increasing
          unit: kWh
        - address: ET0PE
          device_class: energy
          name: Cumulative energy (updated 1)
          response_idx: 0
          state_class: total_increasing
          unit: kWh
'''


@pytest.mark.usefixtures('mock_config')
@pytest.mark.config_yaml(CONFIG_YAML)
def test_config_payload_update(
    mock_serial: MockSerialT, mock_mqtt: MockMqttT
) -> None:
    '''
    Tests for configuration payload to be sent again once it changes (e.g.
    through interpolation).
    '''
    main()
    mock_serial['_send'].assert_has_calls(
        [call(x['receive_bytes']) for x in serial_exchange]
    )

    mock_mqtt['publish'].assert_has_calls([
        call(
            topic='homeassistant/sensor/CE301_00123456'
            '/CE301_00123456_ET0PE/config',
            payload=json.dumps(
                {
                    'name': 'Cumulative energy (updated)',
                    'device': {
                        'name': '00123456',
                        'ids': 'CE301_00123456',
                        'model': 'CE301',
                        'sw_version': '12',
                    },
                    'device_class': 'energy',
                    'unique_id': 'CE301_00123456_ET0PE',
                    'default_entity_id': 'CE301_00123456_ET0PE',
                    'unit_of_measurement': 'kWh',
                    'state_class': 'total_increasing',
                    'state_topic': 'homeassistant/sensor/CE301_00123456'
                                   '/CE301_00123456_ET0PE/state',
                    'value_template': '{{ value_json.value }}',
                }
            ),
            retain=True,
        ),
    ])

    mock_mqtt['publish'].assert_has_calls([
        call(
            topic='homeassistant/sensor/CE301_00123456'
            '/CE301_00123456_ET0PE/config',
            payload=json.dumps(
                {
                    'name': 'Cumulative energy (updated 1)',
                    'device': {
                        'name': '00123456',
                        'ids': 'CE301_00123456',
                        'model': 'CE301',
                        'sw_version': '12',
                    },
                    'device_class': 'energy',
                    'unique_id': 'CE301_00123456_ET0PE',
                    'default_entity_id': 'CE301_00123456_ET0PE',
                    'unit_of_measurement': 'kWh',
                    'state_class': 'total_increasing',
                    'state_topic': 'homeassistant/sensor/CE301_00123456'
                                   '/CE301_00123456_ET0PE/state',
                    'value_template': '{{ value_json.value }}',
                }
            ),
            retain=True,
        ),
    ])
