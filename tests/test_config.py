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
tbd
'''

from unittest.mock import mock_open, patch
import pytest
from energomera_hass_mqtt import EnergomeraConfig, EnergomeraConfigError


def test_valid_config_file():
    '''
    tbd
    '''
    valid_config_yaml = '''
        meter:
          port: dummy_serial
          password: dummy_password
        mqtt:
          host: mqtt_dummy_host
          user: mqtt_dummy_user
          password: mqtt_dummy_password
        parameters:
            - name: dummy_param
              address: dummy_addr
              device_class: dummy_class
              state_class: dummy_state
              unit: dummy
    '''
    valid_config = {
        'meter': {
            'port': 'dummy_serial',
            'password': 'dummy_password',
        },
        'mqtt': {
            'host': 'mqtt_dummy_host',
            'user': 'mqtt_dummy_user',
            'password': 'mqtt_dummy_password',
            'hass_discovery_prefix': 'homeassistant',
        },
        'parameters': [
            {
                'name': 'dummy_param',
                'address': 'dummy_addr',
                'device_class': 'dummy_class',
                'state_class': 'dummy_state',
                'unit': 'dummy',
                'additional_data': None,
                'entity_name': None,
                'response_idx': None,
            },
        ],
    }

    with patch('builtins.open', mock_open(read_data=valid_config_yaml)):
        config = EnergomeraConfig(config_file='dummy')
        assert isinstance(config.of, dict)
        assert config.of == valid_config


def test_invalid_config_file():
    '''
    tbd
    '''
    with patch('builtins.open', mock_open(read_data='')):
        with pytest.raises(EnergomeraConfigError):
            EnergomeraConfig('dummy')
