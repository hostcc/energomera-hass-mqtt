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

# pylint: disable=too-many-lines
'''
Tests for 'energomera_hass_mqtt' package
'''
import sys
import json
from unittest.mock import call, patch, mock_open
from functools import reduce
from freezegun import freeze_time
import pytest
import asyncio_mqtt.client
import iec62056_21.transports
from energomera_hass_mqtt import main

# Serial exchange to simulate - `send_bytes` will be simulated as if received
# from the device, `receive_bytes` is what expected to be sent by the package.
# The directional view here is from device standpoint.
# The data is taken from real device's traffic with only some parts obfuscated.
serial_exchange = [
    {
        'receive_bytes': b'/?!\r\n',
        'send_bytes': b'/EKT5CE301v12\r\n',
    },
    {
        'receive_bytes': b'\x06051\r\n',
        'send_bytes': b'\x01P0\x02(777777)\x03\x20',
    },
    {
        'receive_bytes': b'\x01P1\x02(dummy)\x03\x03',
        'send_bytes': b'\x06',
    },
    {
        'receive_bytes': b'\x01R1\x02HELLO()\x03M',
        'send_bytes': b'\x02HELLO(2,CE301,12,00123456,dummy)\r\n\x03\x01',
    },
    {
        'receive_bytes': b'\x01R1\x02ET0PE()\x037',
        'send_bytes':
            b'\x02ET0PE(16907.9477764)\r\n'
            b'ET0PE(11504.3875082)\r\n'
            b'ET0PE(3628.2698795)\r\n'
            b'ET0PE(1775.2903887)\r\n'
            b'ET0PE(0.0)\r\n'
            b'ET0PE(0.0)\r\n\x03\x04',
    },
    {
        'receive_bytes': b'\x01R1\x02ECMPE()\x03C',
        'send_bytes':
            b'\x02ECMPE(357.8505119)\r\n'
            b'ECMPE(208.6539992)\r\n'
            b'ECMPE(106.9769041)\r\n'
            b'ECMPE(42.2196086)\r\n'
            b'ECMPE(0.0)\r\n'
            b'ECMPE(0.0)\r\n'
            b'\x03E',
    },
    {
        'receive_bytes': b'\x01R1\x02ENMPE(04.22)\x03D',
        'send_bytes':
            b'\x02ENMPE(16550.0972645)\r\n'
            b'ENMPE(11295.733509)\r\n'
            b'ENMPE(3521.2929754)\r\n'
            b'ENMPE(1733.0707801)\r\n'
            b'ENMPE(0.0)\r\n'
            b'ENMPE(0.0)\r\n'
            b'\x03*',
    },
    {
        'receive_bytes': b'\x01R1\x02EAMPE(04.22)\x037',
        'send_bytes':
            b'\x02EAMPE(477.8955487)\r\n'
            b'EAMPE(325.201782)\r\n'
            b'EAMPE(103.4901674)\r\n'
            b'EAMPE(49.2035993)\r\n'
            b'EAMPE(0.0)\r\n'
            b'EAMPE(0.0)\r\n'
            b'\x03\x04',
    },
    {
        'receive_bytes': b'\x01R1\x02ECDPE()\x03:',
        'send_bytes':
            b'\x02ECDPE(13.7433546)\r\n'
            b'ECDPE(5.5472398)\r\n'
            b'ECDPE(5.7096121)\r\n'
            b'ECDPE(2.4865027)\r\n'
            b'ECDPE(0.0)\r\n'
            b'ECDPE(0.0)\r\n'
            b'\x03M',
    },
    {
        'receive_bytes': b'\x01R1\x02POWPP()\x03o',
        'send_bytes':
            b'\x02POWPP(0.0592)\r\n'
            b'POWPP(0.4402)\r\n'
            b'POWPP(0.054)\r\n'
            b'\x03J',
    },
    {
        'receive_bytes': b'\x01R1\x02POWEP()\x03d',
        'send_bytes': b'\x02POWEP(0.5266)\r\n\x03\'',
    },
    {
        'receive_bytes': b'\x01R1\x02VOLTA()\x03_',
        'send_bytes':
            b'\x02VOLTA(233.751)\r\n'
            b'VOLTA(235.418)\r\n'
            b'VOLTA(234.796)\r\n'
            b'\x03\x02',
    },
    {
        'receive_bytes': b'\x01R1\x02VNULL()\x03j',
        'send_bytes': b'\x02VNULL(0)\r\n\x03,',
    },
    {
        'receive_bytes': b'\x01R1\x02CURRE()\x03Z',
        'send_bytes':
            b'\x02CURRE(1.479)\r\n'
            b'CURRE(2.8716)\r\n'
            b'CURRE(0.782)\r\n'
            b'\x03v',
    },
    {
        'receive_bytes': b'\x01R1\x02FREQU()\x03\\',
        'send_bytes': b'\x02FREQU(49.96)\r\n\x03x',
    },
    {
        'receive_bytes': b'\x01R1\x02ECDPE()\x03:',
        'send_bytes':
            b'\x02ECDPE(13.7433546)\r\n'
            b'ECDPE(5.5472398)\r\n'
            b'ECDPE(5.7096121)\r\n'
            b'ECDPE(2.4865027)\r\n'
            b'ECDPE(0.0)\r\n'
            b'ECDPE(0.0)\r\n'
            b'\x03M',
    },
    # Entry for HASS sensor with auto-indexed name
    {
        'receive_bytes': b'\x01R1\x02CURRE()\x03Z',
        'send_bytes':
            b'\x02CURRE(1.479)\r\n'
            b'CURRE(2.8716)\r\n'
            b'CURRE(0.782)\r\n'
            b'\x03v',
    },
    # Entry for HASS sensor with fallback names
    {
        'receive_bytes': b'\x01R1\x02CURRE()\x03Z',
        'send_bytes':
            b'\x02CURRE(1.479)\r\n'
            b'CURRE(2.8716)\r\n'
            b'CURRE(0.782)\r\n'
            b'\x03v',
    },
]

# Expected MQTT publish calls of the sequence and contents corresponds to the
# serial exchange above
mqtt_publish_calls = [
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_ET0PE/config',
        payload=json.dumps(
            {
                'name': 'Cumulative energy',
                'device': {
                    'name': '00123456',
                    'ids': 'CE301_00123456',
                    'model': 'CE301',
                    'sw_version': '12',
                },
                'device_class': 'energy',
                'unique_id': 'CE301_00123456_ET0PE',
                'unit_of_measurement': 'kWh',
                'state_class': 'total_increasing',
                'state_topic': 'homeassistant/sensor/CE301_00123456'
                               '/CE301_00123456_ET0PE/state',
                'value_template': '{{ value_json.value }}',
            }
        ),
        retain=True,
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456/CE301_00123456_ET0PE/state',
        payload=json.dumps({'value': '16907.9477764'}),
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_ECMPE/config',
        payload=json.dumps(
            {
                'name': 'Monthly energy',
                'device': {
                    'name': '00123456',
                    'ids': 'CE301_00123456',
                    'model': 'CE301',
                    'sw_version': '12',
                },
                'device_class': 'energy',
                'unique_id': 'CE301_00123456_ECMPE',
                'unit_of_measurement': 'kWh',
                'state_class': 'total',
                'state_topic': 'homeassistant/sensor/CE301_00123456'
                               '/CE301_00123456_ECMPE/state',
                'value_template': '{{ value_json.value }}',
            }
        ),
        retain=True,
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456/CE301_00123456_ECMPE/state',
        payload=json.dumps({'value': '357.8505119'}),
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_ENMPE_PREV_MONTH/config',
        payload=json.dumps(
            {
                'name': 'Cumulative energy, previous month',
                'device': {
                    'name': '00123456',
                    'ids': 'CE301_00123456',
                    'model': 'CE301',
                    'sw_version': '12',
                },
                'device_class': 'energy',
                'unique_id': 'CE301_00123456_ENMPE_PREV_MONTH',
                'unit_of_measurement': 'kWh',
                'state_class': 'total_increasing',
                'state_topic': 'homeassistant/sensor/CE301_00123456'
                               '/CE301_00123456_ENMPE_PREV_MONTH/state',
                'value_template': '{{ value_json.value }}',
            }
        ),
        retain=True,
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_ENMPE_PREV_MONTH/state',
        payload=json.dumps({'value': '16550.0972645'}),
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_ECMPE_PREV_MONTH/config',
        payload=json.dumps(
            {
                'name': 'Previous month energy',
                'device': {
                    'name': '00123456',
                    'ids': 'CE301_00123456',
                    'model': 'CE301',
                    'sw_version': '12',
                },
                'device_class': 'energy',
                'unique_id': 'CE301_00123456_ECMPE_PREV_MONTH',
                'unit_of_measurement': 'kWh',
                'state_class': 'total',
                'state_topic': 'homeassistant/sensor/CE301_00123456'
                               '/CE301_00123456_ECMPE_PREV_MONTH/state',
                'value_template': '{{ value_json.value }}',
            }
        ),
        retain=True,
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_ECMPE_PREV_MONTH/state',
        payload=json.dumps({'value': '477.8955487'}),
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_ECDPE/config',
        payload=json.dumps(
            {
                'name': 'Daily energy',
                'device': {
                    'name': '00123456',
                    'ids': 'CE301_00123456',
                    'model': 'CE301',
                    'sw_version': '12',
                },
                'device_class': 'energy',
                'unique_id': 'CE301_00123456_ECDPE',
                'unit_of_measurement': 'kWh',
                'state_class': 'total',
                'state_topic': 'homeassistant/sensor/CE301_00123456'
                               '/CE301_00123456_ECDPE/state',
                'value_template': '{{ value_json.value }}',
            }
        ),
        retain=True,
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456/CE301_00123456_ECDPE/state',
        payload=json.dumps({'value': '13.7433546'}),
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_POWPP_0/config',
        payload=json.dumps(
            {
                'name': 'Active energy, phase A',
                'device': {
                    'name': '00123456',
                    'ids': 'CE301_00123456',
                    'model': 'CE301',
                    'sw_version': '12',
                },
                'device_class': 'power',
                'unique_id': 'CE301_00123456_POWPP_0',
                'unit_of_measurement': 'kW',
                'state_class': 'measurement',
                'state_topic': 'homeassistant/sensor/CE301_00123456'
                               '/CE301_00123456_POWPP_0/state',
                'value_template': '{{ value_json.value }}',
            }
        ),
        retain=True,
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_POWPP_0/state',
        payload=json.dumps({'value': '0.0592'}),
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_POWPP_1/config',
        payload=json.dumps(
            {
                'name': 'Active energy, phase B',
                'device': {
                    'name': '00123456',
                    'ids': 'CE301_00123456',
                    'model': 'CE301',
                    'sw_version': '12',
                },
                'device_class': 'power',
                'unique_id': 'CE301_00123456_POWPP_1',
                'unit_of_measurement': 'kW',
                'state_class': 'measurement',
                'state_topic': 'homeassistant/sensor/CE301_00123456'
                               '/CE301_00123456_POWPP_1/state',
                'value_template': '{{ value_json.value }}',
            }
        ),
        retain=True,
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_POWPP_1/state',
        payload=json.dumps({'value': '0.4402'}),
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_POWPP_2/config',
        payload=json.dumps(
            {
                'name': 'Active energy, phase C',
                'device': {
                    'name': '00123456',
                    'ids': 'CE301_00123456',
                    'model': 'CE301',
                    'sw_version': '12',
                },
                'device_class': 'power',
                'unique_id': 'CE301_00123456_POWPP_2',
                'unit_of_measurement': 'kW',
                'state_class': 'measurement',
                'state_topic': 'homeassistant/sensor/CE301_00123456'
                               '/CE301_00123456_POWPP_2/state',
                'value_template': '{{ value_json.value }}',
            }
        ),
        retain=True,
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_POWPP_2/state',
        payload=json.dumps({'value': '0.054'}),
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_POWEP/config',
        payload=json.dumps(
            {
                'name': 'Active energy',
                'device': {
                    'name': '00123456',
                    'ids': 'CE301_00123456',
                    'model': 'CE301',
                    'sw_version': '12',
                },
                'device_class': 'power',
                'unique_id': 'CE301_00123456_POWEP',
                'unit_of_measurement': 'kW',
                'state_class': 'measurement',
                'state_topic': 'homeassistant/sensor/CE301_00123456'
                               '/CE301_00123456_POWEP/state',
                'value_template': '{{ value_json.value }}',
            }
        ),
        retain=True,
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456/CE301_00123456_POWEP/state',
        payload=json.dumps({'value': '0.5266'}),
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_VOLTA_0/config',
        payload=json.dumps(
            {
                'name': 'Voltage, phase A',
                'device': {
                    'name': '00123456',
                    'ids': 'CE301_00123456',
                    'model': 'CE301',
                    'sw_version': '12',
                },
                'device_class': 'voltage',
                'unique_id': 'CE301_00123456_VOLTA_0',
                'unit_of_measurement': 'V',
                'state_class': 'measurement',
                'state_topic': 'homeassistant/sensor/CE301_00123456'
                               '/CE301_00123456_VOLTA_0/state',
                'value_template': '{{ value_json.value }}',
            }
        ),
        retain=True,
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_VOLTA_0/state',
        payload=json.dumps({'value': '233.751'}),
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_VOLTA_1/config',
        payload=json.dumps(
            {
                'name': 'Voltage, phase B',
                'device': {
                    'name': '00123456',
                    'ids': 'CE301_00123456',
                    'model': 'CE301',
                    'sw_version': '12',
                },
                'device_class': 'voltage',
                'unique_id': 'CE301_00123456_VOLTA_1',
                'unit_of_measurement': 'V',
                'state_class': 'measurement',
                'state_topic': 'homeassistant/sensor/CE301_00123456'
                               '/CE301_00123456_VOLTA_1/state',
                'value_template': '{{ value_json.value }}',
            }
        ),
        retain=True,
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_VOLTA_1/state',
        payload=json.dumps({'value': '235.418'}),
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_VOLTA_2/config',
        payload=json.dumps(
            {
                'name': 'Voltage, phase C',
                'device': {
                    'name': '00123456',
                    'ids': 'CE301_00123456',
                    'model': 'CE301',
                    'sw_version': '12',
                },
                'device_class': 'voltage',
                'unique_id': 'CE301_00123456_VOLTA_2',
                'unit_of_measurement': 'V',
                'state_class': 'measurement',
                'state_topic': 'homeassistant/sensor/CE301_00123456'
                               '/CE301_00123456_VOLTA_2/state',
                'value_template': '{{ value_json.value }}',
            }
        ),
        retain=True,
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_VOLTA_2/state',
        payload=json.dumps({'value': '234.796'}),
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_VNULL/config',
        payload=json.dumps(
            {
                'name': 'Neutral voltage',
                'device': {
                    'name': '00123456',
                    'ids': 'CE301_00123456',
                    'model': 'CE301',
                    'sw_version': '12',
                },
                'device_class': 'voltage',
                'unique_id': 'CE301_00123456_VNULL',
                'unit_of_measurement': 'V',
                'state_class': 'measurement',
                'state_topic': 'homeassistant/sensor/CE301_00123456'
                               '/CE301_00123456_VNULL/state',
                'value_template': '{{ value_json.value }}',
            }
        ),
        retain=True,
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456/CE301_00123456_VNULL/state',
        payload=json.dumps({'value': '0'}),
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_CURRE_0/config',
        payload=json.dumps(
            {
                'name': 'Current, phase A',
                'device': {
                    'name': '00123456',
                    'ids': 'CE301_00123456',
                    'model': 'CE301',
                    'sw_version': '12',
                },
                'device_class': 'current',
                'unique_id': 'CE301_00123456_CURRE_0',
                'unit_of_measurement': 'A',
                'state_class': 'measurement',
                'state_topic': 'homeassistant/sensor/CE301_00123456'
                               '/CE301_00123456_CURRE_0/state',
                'value_template': '{{ value_json.value }}',
            }
        ),
        retain=True,
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_CURRE_0/state',
        payload=json.dumps({'value': '1.479'}),
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_CURRE_1/config',
        payload=json.dumps(
            {
                'name': 'Current, phase B',
                'device': {
                    'name': '00123456',
                    'ids': 'CE301_00123456',
                    'model': 'CE301',
                    'sw_version': '12',
                },
                'device_class': 'current',
                'unique_id': 'CE301_00123456_CURRE_1',
                'unit_of_measurement': 'A',
                'state_class': 'measurement',
                'state_topic': 'homeassistant/sensor/CE301_00123456'
                               '/CE301_00123456_CURRE_1/state',
                'value_template': '{{ value_json.value }}',
            }
        ),
        retain=True,
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_CURRE_1/state',
        payload=json.dumps({'value': '2.8716'}),
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_CURRE_2/config',
        payload=json.dumps(
            {
                'name': 'Current, phase C',
                'device': {
                    'name': '00123456',
                    'ids': 'CE301_00123456',
                    'model': 'CE301',
                    'sw_version': '12',
                },
                'device_class': 'current',
                'unique_id': 'CE301_00123456_CURRE_2',
                'unit_of_measurement': 'A',
                'state_class': 'measurement',
                'state_topic': 'homeassistant/sensor/CE301_00123456'
                               '/CE301_00123456_CURRE_2/state',
                'value_template': '{{ value_json.value }}',
            }
        ),
        retain=True,
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_CURRE_2/state',
        payload=json.dumps({'value': '0.782'}),
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_FREQU/config',
        payload=json.dumps(
            {
                'name': 'Frequency',
                'device': {
                    'name': '00123456',
                    'ids': 'CE301_00123456',
                    'model': 'CE301',
                    'sw_version': '12',
                },
                'device_class': 'frequency',
                'unique_id': 'CE301_00123456_FREQU',
                'unit_of_measurement': 'Hz',
                'state_class': 'measurement',
                'state_topic': 'homeassistant/sensor/CE301_00123456'
                               '/CE301_00123456_FREQU/state',
                'value_template': '{{ value_json.value }}',
            }
        ),
        retain=True,
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_FREQU/state',
        payload=json.dumps({'value': '49.96'}),
    ),
    # MQTT calls for HASS entry with auto-indexed name
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_CURRE_INDEXED_0/config',
        payload=json.dumps(
            {
                'name': 'Current 0',
                'device': {
                    'name': '00123456',
                    'ids': 'CE301_00123456',
                    'model': 'CE301',
                    'sw_version': '12',
                },
                'device_class': 'current',
                'unique_id': 'CE301_00123456_CURRE_INDEXED_0',
                'unit_of_measurement': 'A',
                'state_class': 'measurement',
                'state_topic': 'homeassistant/sensor/CE301_00123456'
                               '/CE301_00123456_CURRE_INDEXED_0/state',
                'value_template': '{{ value_json.value }}',
            }
        ),
        retain=True,
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_CURRE_INDEXED_0/state',
        payload=json.dumps({'value': '1.479'}),
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_CURRE_INDEXED_1/config',
        payload=json.dumps(
            {
                'name': 'Current 1',
                'device': {
                    'name': '00123456',
                    'ids': 'CE301_00123456',
                    'model': 'CE301',
                    'sw_version': '12',
                },
                'device_class': 'current',
                'unique_id': 'CE301_00123456_CURRE_INDEXED_1',
                'unit_of_measurement': 'A',
                'state_class': 'measurement',
                'state_topic': 'homeassistant/sensor/CE301_00123456'
                               '/CE301_00123456_CURRE_INDEXED_1/state',
                'value_template': '{{ value_json.value }}',
            }
        ),
        retain=True,
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_CURRE_INDEXED_1/state',
        payload=json.dumps({'value': '2.8716'}),
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_CURRE_INDEXED_2/config',
        payload=json.dumps(
            {
                'name': 'Current 2',
                'device': {
                    'name': '00123456',
                    'ids': 'CE301_00123456',
                    'model': 'CE301',
                    'sw_version': '12',
                },
                'device_class': 'current',
                'unique_id': 'CE301_00123456_CURRE_INDEXED_2',
                'unit_of_measurement': 'A',
                'state_class': 'measurement',
                'state_topic': 'homeassistant/sensor/CE301_00123456'
                               '/CE301_00123456_CURRE_INDEXED_2/state',
                'value_template': '{{ value_json.value }}',
            }
        ),
        retain=True,
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_CURRE_INDEXED_2/state',
        payload=json.dumps({'value': '0.782'}),
    ),
    # MQTT calls for HASS entry with fallback names
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_CURRE_INDEXED_FALLBACK_0/config',
        payload=json.dumps(
            {
                'name': 'Current, phase A',
                'device': {
                    'name': '00123456',
                    'ids': 'CE301_00123456',
                    'model': 'CE301',
                    'sw_version': '12',
                },
                'device_class': 'current',
                'unique_id': 'CE301_00123456_CURRE_INDEXED_FALLBACK_0',
                'unit_of_measurement': 'A',
                'state_class': 'measurement',
                'state_topic': 'homeassistant/sensor/CE301_00123456'
                               '/CE301_00123456_CURRE_INDEXED_FALLBACK_0'
                               '/state',
                'value_template': '{{ value_json.value }}',
            }
        ),
        retain=True,
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_CURRE_INDEXED_FALLBACK_0/state',
        payload=json.dumps({'value': '1.479'}),
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_CURRE_INDEXED_FALLBACK_1/config',
        payload=json.dumps(
            {
                'name': 'CURRE 1',
                'device': {
                    'name': '00123456',
                    'ids': 'CE301_00123456',
                    'model': 'CE301',
                    'sw_version': '12',
                },
                'device_class': 'current',
                'unique_id': 'CE301_00123456_CURRE_INDEXED_FALLBACK_1',
                'unit_of_measurement': 'A',
                'state_class': 'measurement',
                'state_topic': 'homeassistant/sensor/CE301_00123456'
                               '/CE301_00123456_CURRE_INDEXED_FALLBACK_1'
                               '/state',
                'value_template': '{{ value_json.value }}',
            }
        ),
        retain=True,
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_CURRE_INDEXED_FALLBACK_1/state',
        payload=json.dumps({'value': '2.8716'}),
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_CURRE_INDEXED_FALLBACK_2/config',
        payload=json.dumps(
            {
                'name': 'CURRE 2',
                'device': {
                    'name': '00123456',
                    'ids': 'CE301_00123456',
                    'model': 'CE301',
                    'sw_version': '12',
                },
                'device_class': 'current',
                'unique_id': 'CE301_00123456_CURRE_INDEXED_FALLBACK_2',
                'unit_of_measurement': 'A',
                'state_class': 'measurement',
                'state_topic': 'homeassistant/sensor/CE301_00123456'
                               '/CE301_00123456_CURRE_INDEXED_FALLBACK_2'
                               '/state',
                'value_template': '{{ value_json.value }}',
            }
        ),
        retain=True,
    ),
    call(
        topic='homeassistant/sensor/CE301_00123456'
        '/CE301_00123456_CURRE_INDEXED_FALLBACK_2/state',
        payload=json.dumps({'value': '0.782'}),
    ),
    call(
        topic='homeassistant/binary_sensor/CE301_00123456'
        '/CE301_00123456_IS_ONLINE/config',
        payload=json.dumps(
            {
                'name': 'Meter online status',
                'device': {
                    'name': '00123456',
                    'ids': 'CE301_00123456',
                    'model': 'CE301',
                    'sw_version': '12',
                },
                'device_class': 'power',
                'unique_id': 'CE301_00123456_IS_ONLINE',
                'state_topic': 'homeassistant/binary_sensor/CE301_00123456'
                               '/CE301_00123456_IS_ONLINE'
                               '/state',
                'value_template': '{{ value_json.value }}',
            }
        ),
        retain=True,
    ),
    call(
        topic='homeassistant/binary_sensor/CE301_00123456'
        '/CE301_00123456_IS_ONLINE/state',
        payload=json.dumps({'value': 'on'}),
        will=dict(
            topic='homeassistant/binary_sensor/CE301_00123456'
            '/CE301_00123456_IS_ONLINE/state',
            payload=json.dumps({'value': 'off'}),
        ),
    ),
]


def run_main():
    '''
    Executes the meter client with given configuration.
    '''

    config_yaml = '''
        general:
            oneshot: true
        meter:
          port: dummy_serial
          password: dummy
          timeout: 1
        mqtt:
          host: mqtt_dummy_host
          user: mqtt_dummy_user
          password: mqtt_dummy_password
        parameters:
            - address: ET0PE
              device_class: energy
              name: Cumulative energy
              response_idx: 0
              state_class: total_increasing
              unit: kWh
            - address: ECMPE
              device_class: energy
              name: Monthly energy
              response_idx: 0
              state_class: total
              unit: kWh
            - additional_data: '{{ energomera_prev_month }}'
              address: ENMPE
              device_class: energy
              entity_name: ENMPE_PREV_MONTH
              name: Cumulative energy, previous month
              response_idx: 0
              state_class: total_increasing
              unit: kWh
            - additional_data: '{{ energomera_prev_month }}'
              address: EAMPE
              device_class: energy
              entity_name: ECMPE_PREV_MONTH
              name: Previous month energy
              response_idx: 0
              state_class: total
              unit: kWh
            - address: ECDPE
              device_class: energy
              name: Daily energy
              response_idx: 0
              state_class: total
              unit: kWh
            - address: POWPP
              device_class: power
              name:
                  - Active energy, phase A
                  - Active energy, phase B
                  - Active energy, phase C
              state_class: measurement
              unit: kW
            - address: POWEP
              device_class: power
              name: Active energy
              state_class: measurement
              unit: kW
            - address: VOLTA
              device_class: voltage
              name:
              - Voltage, phase A
              - Voltage, phase B
              - Voltage, phase C
              state_class: measurement
              unit: V
            - address: VNULL
              device_class: voltage
              name: Neutral voltage
              state_class: measurement
              unit: V
            - address: CURRE
              device_class: current
              name:
              - Current, phase A
              - Current, phase B
              - Current, phase C
              state_class: measurement
              unit: A
            - address: FREQU
              device_class: frequency
              name: Frequency
              state_class: measurement
              unit: Hz
            - address: ECDPE
              device_class: energy
              name: Daily energy
              response_idx: 100
              state_class: total
              unit: kWh
            - address: CURRE
              device_class: current
              name: Current
              state_class: measurement
              entity_name: CURRE_INDEXED
              unit: A
            - address: CURRE
              device_class: current
              name:
              - Current, phase A
              state_class: measurement
              unit: A
              entity_name: CURRE_INDEXED_FALLBACK
    '''

    # Perform communication with the device and issue MQTT calls
    with patch('builtins.open', mock_open(read_data=config_yaml)):
        with patch.object(sys, 'argv', ['dummy']):
            return main.main()


@freeze_time("2022-05-01")
# Mock the calls we interested in
@patch.object(asyncio_mqtt.client.Client, 'publish')
@patch.object(iec62056_21.transports.SerialTransport, '_send')
@patch.object(iec62056_21.transports.SerialTransport, '_recv')
# Mock certain methods of 'iec62056_21' package (serial communications) and
# 'asyncio_mqtt' (MQTT) to prevent serial/networking calls
@patch.object(iec62056_21.transports.SerialTransport, 'switch_baudrate')
@patch.object(iec62056_21.transports.SerialTransport, 'disconnect')
@patch.object(iec62056_21.transports.SerialTransport, 'connect')
@patch.object(asyncio_mqtt.client.Client, 'connect')
def run_main_with_mocks(
    _mqtt_connect_mock, _serial_connect_mock, _serial_disconnect_mock,
    _serial_switch_baudrate_mock,
    serial_recv_mock, serial_send_mock, mqtt_publish_mock,
    simulate_timeout=False
):
    '''
    Execute the main flow interacting with the device and MQTT.
    '''

    # Simulate data received from serial port.
    mocked_serial_exchange = [
        # Accessing `bytes` by subscription or via iterator (what `side_effect`
        # internally does for iterable) will result in integer, so to retain
        # the type the nested arrays each containing single `bytes` is used
        bytes([y]) for y in
        # Produces array of bytes of all serial exchange fragments
        reduce(
            lambda x, y: x + y,
            [x['send_bytes'] for x in serial_exchange]
        )
    ]

    if simulate_timeout:
        # Simulate timeout occured at the end of mocked serial exchange. Some
        # initial packets are needed to grab meter identification so we can
        # test online sensor (it depends on those)
        mocked_serial_exchange[-1] = TimeoutError

    serial_recv_mock.side_effect = mocked_serial_exchange

    run_main()
    # Resulting calls sending data over serial and doing MQTT publishes
    return mqtt_publish_mock.call_args_list, serial_send_mock.call_args_list


(mqtt_publish_call_args, serial_send_call_args) = run_main_with_mocks()


def generate_mqtt_tests(call_args):
    '''
    Generates data for `@pytest.mark.parametrize` to instantiate multiple tests
    for MQTT publishes, each test per specific MQTT call - makes easier to see
    particular call differs from expected one.
    '''
    values = []
    ids = []
    for (exp, arg) in zip(mqtt_publish_calls, call_args):
        values.append((arg, exp))
        ids.append(exp.kwargs.get('topic', str(exp)))

    return {'argvalues': values, 'ids': ids}


def generate_serial_tests(call_args):
    '''
    Generates data for `@pytest.mark.parametrize` to instantiate multiple tests
    for serial sends, each test per specific MQTT call - makes easier to see
    particular call differs from expected one.
    '''

    values = []
    ids = []

    for (exp, arg) in zip([x['receive_bytes'] for x in serial_exchange],
                          call_args):
        values.append((arg, call(exp)))
        ids.append(str(exp))

    return {'argvalues': values, 'ids': ids}


@pytest.mark.parametrize('serial_call,serial_expected',
                         **generate_serial_tests(serial_send_call_args))
def test_serial_send(serial_call, serial_expected):
    '''
    Tests the data sent over serial.
    '''
    assert serial_call == serial_expected


@pytest.mark.parametrize('mqtt_call,mqtt_expected',
                         **generate_mqtt_tests(mqtt_publish_call_args))
def test_mqtt_publish(mqtt_call, mqtt_expected):
    '''
    Tests the data published to MQTT.
    '''
    assert mqtt_call == mqtt_expected


@patch.object(asyncio_mqtt.client.Client, 'publish')
@patch.object(asyncio_mqtt.client.Client, 'connect')
@patch.object(iec62056_21.transports.SerialTransport, '_recv')
@patch.object(iec62056_21.transports.SerialTransport, '_send')
@patch.object(iec62056_21.transports.SerialTransport, 'connect')
def test_timeout(_serial_connect_mock, _serial_send_mock,
                 serial_recv_mock, _mqtt_connect_mock, _mqtt_publish_mock):
    '''
    Tests for timeout handling.
    '''
    serial_recv_mock.return_value = None
    run_main()


def test_online_sensor():
    '''
    Tests for handling pseudo online sensor under timeout condition.
    '''
    (mqtt_publish_call_args_for_timeout, _) = run_main_with_mocks(
        simulate_timeout=True
    )

    assert call(
        topic='homeassistant/binary_sensor/CE301_00123456'
        '/CE301_00123456_IS_ONLINE/state',
        payload=json.dumps({'value': 'off'}),
        will=dict(
            topic='homeassistant/binary_sensor/CE301_00123456'
            '/CE301_00123456_IS_ONLINE/state',
            payload=json.dumps({'value': 'off'}),
        ),
    ) in mqtt_publish_call_args_for_timeout
