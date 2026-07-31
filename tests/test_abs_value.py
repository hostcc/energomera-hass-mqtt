# Copyright (c) 2026 Ilia Sotnikov
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
Tests for per-parameter abs_value conversion.
'''
from __future__ import annotations
from typing import Any, Dict, List
import json
import logging
from unittest.mock import call
import pytest
from conftest import (
    CONFIG_YAML_BASE, MockMqttT, SERIAL_EXCHANGE_BASE
)
from energomera_hass_mqtt.main import main

POWEP_REQUEST: Dict[str, bytes] = {
    'receive_bytes': b'\x01R1\x02POWEP()\x03d',
}


def _config_yaml(abs_value: bool) -> str:
    abs_value_yaml = 'true' if abs_value else 'false'
    return CONFIG_YAML_BASE + f'''
    parameters:
        - address: POWEP
          device_class: power
          name: Active power abs
          state_class: measurement
          unit: kW
          abs_value: {abs_value_yaml}
'''


def _serial_exchange(value: str) -> List[Dict[str, bytes]]:
    responses = {
        '-1.2345': b'\x02POWEP(-1.2345)\r\n\x03P',
        '-42': b'\x02POWEP(-42)\r\n\x03\t',
        'not-a-number': b'\x02POWEP(not-a-number)\r\n\x03\x0b',
        '-0.5266': b'\x02POWEP(-0.5266)\r\n\x03T',
    }
    return SERIAL_EXCHANGE_BASE + [
        {
            **POWEP_REQUEST,
            'send_bytes': responses[value],
        },
    ]


def _config_payload(*, with_attributes: bool) -> Dict[str, Any]:
    payload = {
        'name': 'Active power abs',
        'device': {
            'name': '00123456',
            'ids': 'CE301_00123456',
            'model': 'CE301',
            'sw_version': '12',
        },
        'device_class': 'power',
        'unique_id': 'CE301_00123456_POWEP',
        'default_entity_id': 'CE301_00123456_POWEP',
        'unit_of_measurement': 'kW',
        'state_class': 'measurement',
        'state_topic': (
            'homeassistant/sensor/CE301_00123456'
            '/CE301_00123456_POWEP/state'
        ),
        'value_template': '{{ value_json.value }}',
    }
    if with_attributes:
        payload['json_attributes_topic'] = (
            'homeassistant/sensor/CE301_00123456'
            '/CE301_00123456_POWEP/state'
        )
        payload['json_attributes_template'] = (
            "{{ {'raw_value': value_json.raw_value} | tojson }}"
        )
    return payload


@pytest.mark.usefixtures('mock_config', 'mock_serial')
@pytest.mark.config_yaml(_config_yaml(True))
@pytest.mark.serial_exchange(_serial_exchange('-1.2345'))
def test_abs_value_float(mock_mqtt: MockMqttT) -> None:
    '''
    Tests abs_value conversion for a negative float reading.
    '''
    main()
    mock_mqtt['publish'].assert_has_calls([
        call(
            topic=(
                'homeassistant/sensor/CE301_00123456'
                '/CE301_00123456_POWEP/config'
            ),
            payload=json.dumps(_config_payload(with_attributes=True)),
            retain=True,
        ),
        call(
            topic=(
                'homeassistant/sensor/CE301_00123456'
                '/CE301_00123456_POWEP/state'
            ),
            payload=json.dumps({
                'value': '1.2345',
                'raw_value': '-1.2345',
            }),
        ),
    ])


@pytest.mark.usefixtures('mock_config', 'mock_serial')
@pytest.mark.config_yaml(_config_yaml(True))
@pytest.mark.serial_exchange(_serial_exchange('-42'))
def test_abs_value_integer(mock_mqtt: MockMqttT) -> None:
    '''
    Tests abs_value conversion for a negative integer reading.
    '''
    main()
    mock_mqtt['publish'].assert_has_calls([
        call(
            topic=(
                'homeassistant/sensor/CE301_00123456'
                '/CE301_00123456_POWEP/config'
            ),
            payload=json.dumps(_config_payload(with_attributes=True)),
            retain=True,
        ),
        call(
            topic=(
                'homeassistant/sensor/CE301_00123456'
                '/CE301_00123456_POWEP/state'
            ),
            payload=json.dumps({
                'value': '42',
                'raw_value': '-42',
            }),
        ),
    ])


@pytest.mark.usefixtures('mock_config', 'mock_serial')
@pytest.mark.config_yaml(_config_yaml(True))
@pytest.mark.serial_exchange(_serial_exchange('not-a-number'))
def test_abs_value_non_numeric(
    mock_mqtt: MockMqttT, caplog: pytest.LogCaptureFixture
) -> None:
    '''
    Tests abs_value on a non-numeric reading logs a warning and keeps the
    original value without aborting the cycle.
    '''
    with caplog.at_level(logging.WARNING):
        main()

    assert any(
        "Cannot apply abs_value to non-numeric value 'not-a-number'" in msg
        for msg in caplog.messages
    )
    mock_mqtt['publish'].assert_has_calls([
        call(
            topic=(
                'homeassistant/sensor/CE301_00123456'
                '/CE301_00123456_POWEP/config'
            ),
            payload=json.dumps(_config_payload(with_attributes=True)),
            retain=True,
        ),
        call(
            topic=(
                'homeassistant/sensor/CE301_00123456'
                '/CE301_00123456_POWEP/state'
            ),
            payload=json.dumps({'value': 'not-a-number'}),
        ),
    ])
    # Cycle still completes with diagnostic sensors published
    published_topics = [
        c.kwargs.get('topic', c.args[0] if c.args else '')
        for c in mock_mqtt['publish'].call_args_list
    ]
    assert any('CYCLE_DURATION' in topic for topic in published_topics)
    assert any('IS_ONLINE' in topic for topic in published_topics)


@pytest.mark.usefixtures('mock_config', 'mock_serial')
@pytest.mark.config_yaml(_config_yaml(False))
@pytest.mark.serial_exchange(_serial_exchange('-0.5266'))
def test_abs_value_disabled(mock_mqtt: MockMqttT) -> None:
    '''
    Tests that negative readings are published unchanged when abs_value is
    disabled.
    '''
    main()
    mock_mqtt['publish'].assert_has_calls([
        call(
            topic=(
                'homeassistant/sensor/CE301_00123456'
                '/CE301_00123456_POWEP/config'
            ),
            payload=json.dumps(_config_payload(with_attributes=False)),
            retain=True,
        ),
        call(
            topic=(
                'homeassistant/sensor/CE301_00123456'
                '/CE301_00123456_POWEP/state'
            ),
            payload=json.dumps({'value': '-0.5266'}),
        ),
    ])
