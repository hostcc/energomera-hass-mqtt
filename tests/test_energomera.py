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
Tests for 'energomera_hass_mqtt' package
'''
from unittest.mock import call, patch
import logging
import pytest
from conftest import (
    MQTT_PUBLISH_CALLS_COMPLETE, SERIAL_EXCHANGE_COMPLETE,
    SERIAL_EXCHANGE_INIT, MockMqttT, MockSerialT
)
from energomera_hass_mqtt.main import main


@pytest.mark.usefixtures('mock_config')
def test_normal_run(mock_serial: MockSerialT, mock_mqtt: MockMqttT) -> None:
    '''
    Tests for normal program execution validating serial and MQTT exchanges.
    '''
    main()
    mock_mqtt['publish'].assert_has_calls(MQTT_PUBLISH_CALLS_COMPLETE)
    mock_serial['_send'].assert_has_calls(
        [call(x['receive_bytes']) for x in SERIAL_EXCHANGE_COMPLETE]
    )


@pytest.mark.usefixtures('mock_config')
def test_dry_run(
    mock_serial: MockSerialT, mock_mqtt_underlying: MockMqttT,
    monkeypatch: pytest.MonkeyPatch
) -> None:
    '''
    Tests for enabling dry-run mode from command line.
    '''
    monkeypatch.setattr('sys.argv', ['energomera_hass_mqtt', '-a'])
    main()
    # Ensure that no MQTT calls are made are sent
    mock_mqtt_underlying['publish'].assert_not_called()
    mock_mqtt_underlying['__aenter__'].assert_not_called()
    mock_mqtt_underlying['__aexit__'].assert_not_called()
    # While serial exchanges are still made
    mock_serial['_send'].assert_has_calls(
        [call(x['receive_bytes']) for x in SERIAL_EXCHANGE_COMPLETE]
    )


@pytest.mark.usefixtures('mock_config', 'mock_mqtt', 'mock_serial')
def test_debug_run(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    '''
    Tests for enabling debug logging from command line.
    '''
    monkeypatch.setattr('sys.argv', ['energomera_hass_mqtt', '-d'])
    with patch('logging.basicConfig') as mock:
        main()
    mock.assert_called_with(level=logging.DEBUG)


@pytest.mark.usefixtures('mock_serial', 'mock_config', 'mock_mqtt')
@pytest.mark.serial_simulate_timeout(True)
def test_timeout() -> None:
    '''
    Tests for timeout handling, no unhandled exceptions should be raised.
    '''
    main()


@pytest.mark.usefixtures('mock_serial', 'mock_config')
@pytest.mark.parametrize(
    '',
    [
        pytest.param(
            id='no_meter_ids',
            marks=pytest.mark.serial_exchange(
                SERIAL_EXCHANGE_INIT + [{
                    'send_bytes': b'\x02HELLO()\r\n\x03\x5f'
                }]
            )
        ),
        pytest.param(
            id='empty_meter_ids',
            marks=pytest.mark.serial_exchange(
                SERIAL_EXCHANGE_INIT + [{
                    'send_bytes': b'\x02HELLO(,,,,)\r\n\x03\x0f'
                }]
            )
        ),
        pytest.param(
            id='many_meter_ids',
            marks=pytest.mark.serial_exchange(
                SERIAL_EXCHANGE_INIT + [{
                    'send_bytes':
                        b'\x02HELLO(,,,,)\r\nHELLO(dummy)\r\n\x03\x17'
                }]
            )
        ),
    ]
)
def test_no_meter_ids(mock_mqtt: MockMqttT) -> None:
    '''
    Tests for invalid meter IDs handling, no MQTT calls should be made.
    '''
    main()

    # Meter IDs are essential for MQTT messages toward Home Assistant,
    # so no MQTT calls should be made if they are not provided or invalid.
    mock_mqtt['connect'].assert_not_called()
    mock_mqtt['publish'].assert_not_called()
