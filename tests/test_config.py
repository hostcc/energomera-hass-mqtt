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
from __future__ import annotations
# re.Match is not generic in Python 3.8, so it uses the `typing.Match` despite
# it is deprecated since Python 3.9
from typing import cast, Match
import logging
import re
from freezegun import freeze_time
import pytest
from energomera_hass_mqtt import (
    EnergomeraConfig, EnergomeraConfigError, ConfigSchema
)

VALID_CONFIG_YAML = '''
    meter:
      port: dummy_serial
      password: dummy_password
    mqtt:
      host: a_mqtt_host
      port: 1888
      user: a_mqtt_user
      password: mqtt_dummy_password
    parameters:
        - name: dummy_param
          address: dummy_addr
          device_class: dummy_class
          state_class: dummy_state
          unit: dummy
'''


@pytest.mark.usefixtures('mock_config')
@pytest.mark.config_yaml(VALID_CONFIG_YAML)
def test_valid_config_file() -> None:
    '''
    Tests for processing of valid configuration file.
    '''
    valid_config = {
        'general': {
            'oneshot': False,
            'intercycle_delay': 30,
            'logging_level': 'error',
            'include_default_parameters': False,
        },
        'meter': {
            'port': 'dummy_serial',
            'password': 'dummy_password',
            'timeout': 30,
        },
        'mqtt': {
            'host': 'a_mqtt_host',
            'port': 1888,
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
            },
        ],
    }

    config = EnergomeraConfig(config_file='dummy')
    assert isinstance(config.of, ConfigSchema)
    assert config.of == ConfigSchema.model_validate(valid_config)
    assert config.logging_level == logging.ERROR


VALID_CONFIG_DEFAULT_PARAMETERS_YAML = '''
    general:
      include_default_parameters: true
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


@pytest.mark.usefixtures('mock_config')
@pytest.mark.config_yaml(VALID_CONFIG_DEFAULT_PARAMETERS_YAML)
def test_valid_config_file_with_default_parameters() -> None:
    '''
    Tests for processing of valid configuration file that allows including
    default parameters plus adds some custom ones.
    '''
    config = EnergomeraConfig(config_file='dummy')
    assert isinstance(config.of, ConfigSchema)
    # Resulting number of parameters should be combined across default and
    # custom ones
    assert len(config.of.parameters) == 12
    # Verify the last parameter is the custom one
    assert config.of.parameters[-1].name == 'dummy_param'


@pytest.mark.usefixtures('mock_config')
@pytest.mark.config_yaml('')
def test_empty_file() -> None:
    '''
    Tests for processing empty configuration file.
    '''
    with pytest.raises(EnergomeraConfigError):
        EnergomeraConfig('dummy')


@pytest.mark.config_yaml(None)
def test_non_existing_file() -> None:
    '''
    Tests for processing non-existent configuration file.
    '''
    with pytest.raises(EnergomeraConfigError):
        EnergomeraConfig(config_file='non-existent-config-file')


def test_invalid_content() -> None:
    '''
    Tests for invalid configuration content.
    '''
    with pytest.raises(EnergomeraConfigError):
        EnergomeraConfig(content='not-a-yaml')


def test_config_required_params() -> None:
    '''
    Tests for required parameters.
    '''
    with pytest.raises(EnergomeraConfigError) as exc_info:
        EnergomeraConfig()
    assert str(exc_info.value) == (
        "Either 'config_file' or 'content' should be provided"
    )


def test_config_invalid_logging_level() -> None:
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
    with pytest.raises(EnergomeraConfigError) as exc_info:
        EnergomeraConfig(content=invalid_config)
    assert 'general.logging_level: Value error' in str(exc_info.value)


def test_config_empty_parameters_with_no_default_ones() -> None:
    '''
    Tests for catching no parameters are supplied and no default ones are
    enabled
    '''
    invalid_config = '''
        general:
          include_default_parameters: false
        meter:
            port: a-port
            password: a-password
        mqtt:
            host: a-host
        parameters: []
    '''
    with pytest.raises(EnergomeraConfigError) as exc_info:
        EnergomeraConfig(content=invalid_config)
    assert "Value error, 'parameters' should not be empty" in str(
        exc_info.value
    )


INTERPOLATED_CONFIG_YAML = '''
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


@pytest.mark.usefixtures('mock_config')
@pytest.mark.config_yaml(INTERPOLATED_CONFIG_YAML)
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
    frozen_date: str,
    prev_month: str, prev_day: str, older_month: str, older_day: str
) -> None:
    '''
    Verifies for interpolated expressions properly processed when `interpolate`
    method is called repeatedly on single configuration object.
    '''
    with freeze_time(frozen_date):
        config = EnergomeraConfig(config_file='dummy')
        config.interpolate()
        assert (
            config
            .of.parameters[0]
            .additional_data == prev_month
        )
        assert (
            config
            .of.parameters[1]
            .additional_data == prev_day
        )
        assert (
            config
            .of.parameters[2]
            .additional_data == older_month
        )
        assert (
            config
            .of.parameters[3]
            .additional_data == older_day
        )
        assert (
            config
            .of.parameters[4]
            .additional_data == prev_month
        )
        assert (
            config
            .of.parameters[5]
            .additional_data == prev_day
        )


INVALID_INTERPOLATION_CONFIGS_YAML = [
    '''
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
    ''',
    '''
    meter:
      port: dummy_serial
      password: dummy_password
    mqtt:
      host: a_mqtt_host
      user: a_mqtt_user
      password: mqtt_dummy_password
    parameters:
        # Argument with opening bracket missing
        - name: dummy_param2
          address: dummy_addr1
          device_class: dummy_class
          state_class: dummy_state
          unit: dummy
          additional_data: '{{ energomera_prev_day ) }}'
    ''',
    '''
    meter:
      port: dummy_serial
      password: dummy_password
    mqtt:
      host: a_mqtt_host
      user: a_mqtt_user
      password: mqtt_dummy_password
    parameters:
        # Non-numeric argument
        - name: dummy_param3
          address: dummy_addr1
          device_class: dummy_class
          state_class: dummy_state
          unit: dummy
          additional_data: '{{ energomera_prev_day (non-numeric) }}'
    ''',
]


@pytest.mark.usefixtures('mock_config')
@pytest.mark.parametrize('config_yaml', INVALID_INTERPOLATION_CONFIGS_YAML)
def test_config_interpolation_invalid(config_yaml: str) -> None:
    '''
    Verifies the expression interpolation raises exception processing the
    argument having invalid format.
    '''
    with pytest.raises(EnergomeraConfigError):
        config = EnergomeraConfig(content=config_yaml)
        config.interpolate()


def test_config_interpolation_expr_param_re_no_groups() -> None:
    '''
    Verifies processing interpolation expression with associated regexp having
    no capturing groups results in default value.
    '''
    # Cast the `re.match` to drop `Optional` from the return type, so there is
    # no typing error calling method under test
    match = cast(
        Match[str], re.match('dummy pattern', 'dummy pattern')
    )
    # pylint:disable=protected-access
    res = EnergomeraConfig._energomera_re_expr_param_int(match, 100)
    assert res == 100


def test_config_interpolation_expr_param_re_no_match() -> None:
    '''
    Verifies assertion fails when calling the method to process interpolation
    expression arguments directly with non-matching regex.
    '''
    # See the comment above
    match = cast(
        Match[str], re.match('dummy pattern', 'dummy non-matching value')
    )
    with pytest.raises(AssertionError):
        # pylint:disable=protected-access
        EnergomeraConfig._energomera_re_expr_param_int(match, 100)
