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

'''
Tests for online sensor behavior
'''
from __future__ import annotations
from typing import Any
import json
from unittest.mock import call, DEFAULT
import pytest
from conftest import MockMqttT
from energomera_hass_mqtt.main import main


@pytest.mark.usefixtures('mock_config', 'mock_serial')
def test_online_sensor(mock_mqtt: MockMqttT) -> None:
    '''
    Tests for handling online pseudo sensor.
    '''
    online_sensor_off_call = call(
        topic='homeassistant/binary_sensor/CE301_00123456'
        '/CE301_00123456_IS_ONLINE/state',
        payload=json.dumps({'value': 'OFF'}),
    )

    # Verify `MqttClient.will_set()` is called with online sensor payload for
    # 'OFF' value _before_ `MqttClient.connect()` as required by the
    # `paho-mqtt` client,
    # https://github.com/eclipse/paho.mqtt.python/blob/v1.6.0/src/paho/mqtt/client.py#L1647
    # `DEFAULT` is of type `Any` so the return value
    async def trace_connect(*_: Any, **__: Any) -> Any:
        assert (
            mock_mqtt['will_set'].call_args_list[-1] == online_sensor_off_call
        )
        return DEFAULT
    mock_mqtt['connect'].side_effect = trace_connect

    # Perform a normal run
    main()

    # Verify the last call to MQTT contains online sensor being OFF, as set
    # when program finishes
    assert mock_mqtt['publish'].call_args_list[-1] == online_sensor_off_call
