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

"""
Module to instantiate configuration data for `EnergomeraHassMqtt` class from
YAML files with defaults and schema validation.
"""

import logging
from datetime import (date, timedelta)
import re
import yaml
from schema import Schema, Optional, SchemaError, Or, And
from addict import Dict


class EnergomeraConfigError(Exception):
    """
    Exception thrown when configuration processing encounters an error.
    """


class EnergomeraConfig:
    """
    Class representing configuration for `EnergomeraHassMqtt` one.

    :param str config_file: Name of configuration file
    :param str content: Literal content representing the configuration
    """
    @staticmethod
    def _energomera_prev_month():
        """
        Static method to calculate previous month in meter's format.

        :return: Previous month formatted as `<month number>.<year>`
        :rtype: str
        """
        return (
            (date.today().replace(day=1) - timedelta(days=1))
            .strftime('%m.%y')
        )

    @staticmethod
    def _energomera_prev_day():
        """
        Static method to calculate previous day in meter's format.

        :return: Previous day formatted as `<day number>.<month
          number>.<year>`
        :rtype: str
        """
        return (
            (date.today() - timedelta(days=1))
            .strftime('%d.%m.%y')
        )

    # Default parameters to use when configuration file has none
    _default_parameters = [
        dict(address='ET0PE',
             name='Cumulative energy',
             device_class='energy',
             state_class='total_increasing',
             unit='kWh',
             response_idx=0,
             additional_data=None,
             entity_name=None),
        dict(address='ECMPE',
             name='Monthly energy',
             device_class='energy',
             state_class='total',
             unit='kWh',
             response_idx=0,
             additional_data=None,
             entity_name=None),
        dict(address='ENMPE',
             name='Cumulative energy, previous month',
             device_class='energy',
             state_class='total_increasing',
             unit='kWh',
             response_idx=0,
             additional_data='{{ energomera_prev_month }}',
             entity_name='ENMPE_PREV_MONTH'),
        dict(address='EAMPE',
             name='Previous month energy',
             device_class='energy',
             state_class='total',
             unit='kWh',
             response_idx=0,
             additional_data='{{ energomera_prev_month }}',
             entity_name='ECMPE_PREV_MONTH'),
        dict(address='ECDPE',
             name='Daily energy',
             device_class='energy',
             state_class='total',
             unit='kWh',
             response_idx=0,
             additional_data=None,
             entity_name=None),
        dict(address='POWPP',
             name=[
                 'Active energy, phase A',
                 'Active energy, phase B',
                 'Active energy, phase C'
             ],
             device_class='power',
             state_class='measurement',
             unit='kW',
             response_idx=None,
             additional_data=None,
             entity_name=None),
        dict(address='POWEP',
             name='Active energy',
             device_class='power',
             state_class='measurement',
             unit='kW',
             response_idx=None,
             additional_data=None,
             entity_name=None),
        dict(address='VOLTA',
             name=[
                 'Voltage, phase A',
                 'Voltage, phase B',
                 'Voltage, phase C'
             ],
             device_class='voltage',
             state_class='measurement',
             unit='V',
             response_idx=None,
             additional_data=None,
             entity_name=None),
        dict(address='VNULL',
             name='Neutral voltage',
             device_class='voltage',
             state_class='measurement',
             unit='V',
             response_idx=None,
             additional_data=None,
             entity_name=None),
        dict(address='CURRE',
             name=[
                 'Current, phase A',
                 'Current, phase B',
                 'Current, phase C'
             ],
             device_class='current',
             state_class='measurement',
             unit='A',
             response_idx=None,
             additional_data=None,
             entity_name=None),
        dict(address='FREQU',
             name='Frequency',
             device_class='frequency',
             state_class='measurement',
             unit='Hz',
             response_idx=None,
             additional_data=None,
             entity_name=None),
    ]

    _logging_levels = dict(
        critical=logging.CRITICAL,
        error=logging.ERROR,
        warning=logging.WARNING,
        info=logging.INFO,
        debug=logging.DEBUG,
    )

    def _get_schema(self):
        """
        Returns schema for the configuration file.

        :return: The schema to use when validating the configuration
          file's contents
        :rtype: Schema
        """
        general_defaults = Dict(
            oneshot=False,
            intercycle_delay=30,
            logging_level='error',
        )

        return Schema({
            Optional('general', default=general_defaults): Schema({
                # Re-use defaults from `general_defaults`
                Optional('oneshot',
                         default=general_defaults.oneshot): bool,
                Optional('intercycle_delay',
                         default=general_defaults.intercycle_delay): int,
                Optional('logging_level',
                         default=general_defaults.logging_level): And(
                    str,
                    lambda x: x in self._logging_levels,
                    error=f'Invalid logging level - should be one of {", ".join(self._logging_levels.keys())}'
                ),
            }),
            'meter': {
                'port': str,
                'password': str,
            },
            'mqtt': {
                'host': str,
                Optional('user'): str,
                Optional('password'): str,
                Optional('hass_discovery_prefix',
                         default='homeassistant'): str,
            },
            Optional('parameters', default=self._default_parameters): [
                Schema({
                    'address': str,
                    'name': Or(str, list),
                    'device_class': str,
                    'state_class': str,
                    'unit': str,
                    Optional('additional_data', default=None): str,
                    Optional('entity_name', default=None): str,
                    Optional('response_idx', default=None): int,
                }),
            ],
        })

    def __init__(self, config_file=None, content=None):
        """
        Initializes configuration state either from file or content string.

        :param str config_file: Name of configuration file
        :param str content: Configuration contents
        """
        if not config_file and not content:
            raise EnergomeraConfigError(
                "Either 'config_file' or 'content' should be provided"
            )

        try:
            if not content:
                with open(config_file, encoding='ascii') as file:
                    content = file.read()

            config = yaml.safe_load(content)
        except (yaml.YAMLError, OSError) as exc:
            raise EnergomeraConfigError(
                f'Error loading configuration file:\n{str(exc)}'
            ) from None

        try:
            config = self._get_schema().validate(config)
        except SchemaError as exc:
            raise EnergomeraConfigError(
                f'Error validating configuration file:\n{str(exc)}'
            ) from None
        # Store the configuration state as `addict.Dict` so access by (possibly
        # chained) attributes is avavilable
        self._config = Dict(config)

    @property
    def of(self):   # pylint:disable=C0103
        """
        Returns the configuration state

        :return: Configuration state
        :rtype: :class:`Dict`
        """
        return self._config

    @property
    def logging_level(self):
        """
        Returns logging level suitable for `logging` library 

        :return: Logging level
        :rtype: int
        """

        return self._logging_levels.get(self._config.general.logging_level)

    def interpolate(self):
        """
        Interpolates certain expressions in `parameters` section of the
        configuration.

        Supported expressions:

        - ``{{ energomera_prev_month }}``: Previous month in meter's format
        - ``{{ energomera_prev_day }}``: Previous day in meter's format
        """
        for param in self._config.parameters:
            for key, value in param.items():
                if isinstance(value, str):
                    value = re.sub(r'{{\s*energomera_prev_month\s*}}',
                                   self._energomera_prev_month(), value)
                    value = re.sub(r'{{\s*energomera_prev_day\s*}}',
                                   self._energomera_prev_day(), value)
                    param[key] = value
