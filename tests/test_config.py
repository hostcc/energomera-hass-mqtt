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
Tests for `EnergomeraConfig` class.
'''

import logging
from unittest.mock import mock_open, patch
import pytest
from energomera_hass_mqtt import EnergomeraConfig, EnergomeraConfigError


def test_valid_config_file():
    '''
    Tests for processing of valid configuration file.
    '''
    valid_config_yaml = '''
        meter:
          port: dummy_serial
          password: dummy_password
        mqtt:
          host: a_mqtt_host
          user: a_mqtt_user
          password: mqtt_dummy_password
        parameters:
            - name: dummy_param
              address: dummy_addr
              device_class: dummy_class
              state_class: dummy_state
              unit: dummy
    '''
    valid_config = {
        'general': {
            'oneshot': False,
            'intercycle_delay': 30,
            'logging_level': 'error',
        },
        'meter': {
            'port': 'dummy_serial',
            'password': 'dummy_password',
        },
        'mqtt': {
            'host': 'a_mqtt_host',
            'user': 'a_mqtt_user',
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
        assert config.logging_level == logging.ERROR


def test_empty_file():
    '''
    Tests for processing empty configuration file.
    '''
    with patch('builtins.open', mock_open(read_data='')):
        with pytest.raises(EnergomeraConfigError):
            EnergomeraConfig('dummy')


def test_non_existing_file():
    '''
    Tests for processing non-existent configuration file.
    '''
    with pytest.raises(EnergomeraConfigError):
        EnergomeraConfig(config_file='non-existent-config-file')


def test_invalid_content():
    '''
    Tests for invalid configuration content.
    '''
    with pytest.raises(EnergomeraConfigError):
        EnergomeraConfig(content='not-a-yaml')


def test_config_required_params():
    '''
    Tests for required parameters.
    '''
    with pytest.raises(EnergomeraConfigError) as exc_info:
        EnergomeraConfig()
    assert str(exc_info.value) == (
        "Either 'config_file' or 'content' should be provided"
    )


def test_config_invalid_logging_level():
    '''
    Tests for invalid logging level properly reported.
    '''
    invalid_config = '''
        general:
            logging_level: invalid
        meter:
            port: a-port
            password: a-password
        mqtt:
            host: a-host
    '''
    with pytest.raises(EnergomeraConfigError):
        EnergomeraConfig(content=invalid_config)
