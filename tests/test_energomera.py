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
from unittest.mock import call
import pytest
from conftest import MQTT_PUBLISH_CALLS_COMPLETE, SERIAL_EXCHANGE_COMPLETE
from energomera_hass_mqtt.main import main


@pytest.mark.usefixtures('mock_config')
def test_normal_run(mock_serial, mock_mqtt):
    '''
    Tests for normal program execution validating serial and MQTT exchanges.
    '''
    main()
    mock_mqtt['publish'].assert_has_calls(MQTT_PUBLISH_CALLS_COMPLETE)
    mock_serial['_send'].assert_has_calls(
        [call(x['receive_bytes']) for x in SERIAL_EXCHANGE_COMPLETE]
    )


@pytest.mark.usefixtures('mock_serial', 'mock_config')
@pytest.mark.serial_simulate_timeout(True)
def test_timeout():
    '''
    Tests for timeout handling, no unhandled exceptions should be raised.
    '''
    main()
