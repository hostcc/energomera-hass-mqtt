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
from freezegun import freeze_time
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
            'timeout': 30,
        },
        'mqtt': {
            'host': 'a_mqtt_host',
            'user': 'a_mqtt_user',
            'password': 'mqtt_dummy_password',
            'hass_discovery_prefix': 'homeassistant',
            'tls': True,
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


@pytest.fixture(scope='module')
def config_with_interpolations():
    '''
    Provides configuration object with interpolation expressions. To be
    instantiated once per module to verify multiple calls to interpolate over
    single instance of configuration object.
    '''
    interpolated_config_yaml = '''
        meter:
          port: dummy_serial
          password: dummy_password
        mqtt:
          host: a_mqtt_host
          user: a_mqtt_user
          password: mqtt_dummy_password
        parameters:
            - name: dummy_param1
              address: dummy_addr1
              device_class: dummy_class
              state_class: dummy_state
              unit: dummy
              additional_data: '{{ energomera_prev_month }}'
            - name: dummy_param2
              address: dummy_addr1
              device_class: dummy_class
              state_class: dummy_state
              unit: dummy
              additional_data: '{{ energomera_prev_day }}'
            # Argument specifying 5 months ago
            - name: dummy_param3
              address: dummy_addr1
              device_class: dummy_class
              state_class: dummy_state
              unit: dummy
              additional_data: '{{ energomera_prev_month (5) }}'
            # Argument specifying 2 days ago
            - name: dummy_param4
              address: dummy_addr1
              device_class: dummy_class
              state_class: dummy_state
              unit: dummy
              additional_data: '{{ energomera_prev_day (2) }}'
            # Empty argument that falls back to 1 month ago
            - name: dummy_param5
              address: dummy_addr1
              device_class: dummy_class
              state_class: dummy_state
              unit: dummy
              additional_data: '{{ energomera_prev_month () }}'
            # Empty argument with whitespaces only that falls back to 1 day ago
            - name: dummy_param6
              address: dummy_addr1
              device_class: dummy_class
              state_class: dummy_state
              unit: dummy
              additional_data: '{{ energomera_prev_day ( ) }}'
    '''

    with patch('builtins.open', mock_open(read_data=interpolated_config_yaml)):
        config = EnergomeraConfig(config_file='dummy')
    return config


@pytest.mark.parametrize(
    'frozen_date,prev_month,prev_day,older_month,older_day',
    [
        ('2022-05-01', '04.22', '30.04.22', '12.21', '29.04.22'),
        ('2022-05-10', '04.22', '09.05.22', '12.21', '08.05.22'),
        ('2022-06-01', '05.22', '31.05.22', '01.22', '30.05.22'),
        ('2023-01-01', '12.22', '31.12.22', '08.22', '30.12.22'),
    ]
)
def test_config_interpolation_date_change(
    # `pylint` mistekenly treats fixture as re-definition
    # pylint: disable=redefined-outer-name,too-many-arguments
    config_with_interpolations, frozen_date,
    prev_month, prev_day, older_month, older_day
):
    '''
    Verifies for interpolated expressions properly processed when `interpolate`
    method is called repeatedly on single configuration object.
    '''
    with freeze_time(frozen_date):
        config_with_interpolations.interpolate()
        assert (
            config_with_interpolations
            .of.parameters[0]
            .additional_data == prev_month
        )
        assert (
            config_with_interpolations
            .of.parameters[1]
            .additional_data == prev_day
        )
        assert (
            config_with_interpolations
            .of.parameters[2]
            .additional_data == older_month
        )
        assert (
            config_with_interpolations
            .of.parameters[3]
            .additional_data == older_day
        )
        assert (
            config_with_interpolations
            .of.parameters[4]
            .additional_data == prev_month
        )
        assert (
            config_with_interpolations
            .of.parameters[5]
            .additional_data == prev_day
        )


@pytest.fixture
def config_with_invalid_interpolations():
    '''
    Provides configuration object with interpolation expressions having invalid
    argument specified.
    '''
    interpolated_config_yaml = '''
        meter:
          port: dummy_serial
          password: dummy_password
        mqtt:
          host: a_mqtt_host
          user: a_mqtt_user
          password: mqtt_dummy_password
        parameters:
            # Argument with closing bracket missing
            - name: dummy_param1
              address: dummy_addr1
              device_class: dummy_class
              state_class: dummy_state
              unit: dummy
              additional_data: '{{ energomera_prev_day ( }}'
            # Argument with opening bracket missing
            - name: dummy_param2
              address: dummy_addr1
              device_class: dummy_class
              state_class: dummy_state
              unit: dummy
              additional_data: '{{ energomera_prev_day ) }}'
            # Non-numeric argument
            - name: dummy_param3
              address: dummy_addr1
              device_class: dummy_class
              state_class: dummy_state
              unit: dummy
              additional_data: '{{ energomera_prev_day (non-numeric) }}'
    '''
    with patch('builtins.open', mock_open(read_data=interpolated_config_yaml)):
        config = EnergomeraConfig(config_file='dummy')
    return config


# `pylint` mistekenly treats fixture as re-definition
# pylint: disable=redefined-outer-name
def test_config_interpolation_invalid(config_with_invalid_interpolations):
    '''
    Verifies the expression interpolation raises exception processing the
    argument having invalid format.
    '''
    with pytest.raises(EnergomeraConfigError):
        config_with_invalid_interpolations.interpolate()
