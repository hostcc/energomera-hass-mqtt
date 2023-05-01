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
Module to instantiate configuration data for :class:`EnergomeraHassMqtt` class
from YAML files with defaults and schema validation.
"""

import logging
from datetime import date
from copy import deepcopy
import re
from dateutil.relativedelta import relativedelta
import yaml
from schema import Schema, Optional, SchemaError, Or, And
from addict import Dict
from .const import DEFAULT_CONFIG


class EnergomeraConfigError(Exception):
    """
    Exception thrown when configuration processing encounters an error.
    """


class EnergomeraConfig:
    """
    Class representing configuration for :class:`EnergomeraHassMqtt` one.

    :param str config_file: Name of configuration file
    :param str content: Literal content representing the configuration
    """

    @staticmethod
    def _energomera_re_expr_param_int(match, default):
        """
        Static method to be used with ``re.sub()`` as callable processing the
        first match group as the argument to interpolation expression.

        :param re.Match match: Match object provided by ``re.sub``
        :param int default: Default value for the argument
        :return str: Interpolated value for the expression argument
        :rtype: str
        """
        # The method is designed to be called by `re.sub`, protect from being
        # called directly with no re.Match instance provided
        assert match is not None

        try:
            expr = match.group(0)
            arg = match.group(1)
        except IndexError:
            # Match having no groups results in default value, likely the regex
            # has no such
            return default

        # Empty argument results in default value
        if not arg:
            return default

        # Having no opening or closing bracket is an error, the leading and
        # trailing whitespace should be removed in the regex
        if not arg.endswith(')') or not arg.startswith('('):
            raise EnergomeraConfigError(
                f"Wrong argument format '{arg}' in expression '{expr}'"
            )

        # Remove brackets surrounding the value and whitespaces (inner ones)
        arg_content = (arg[1:-1] or '').strip()
        # Empty argument results in default value
        if not arg_content:
            return default

        # Attempt to parse the argument as integer and raise error if it isn't
        try:
            return int(arg_content)
        except ValueError as exc:
            raise EnergomeraConfigError(
                f"Non-numeric argument '{arg_content}' in expression '{expr}'"
            ) from exc

    @staticmethod
    def _energomera_prev_month(match):
        """
        Static method to calculate previous month in meter's format.

        :return: Previous month formatted as ``<month number>.<year>``
        :rtype: str
        """

        months = EnergomeraConfig._energomera_re_expr_param_int(match, 1)
        return (
            (date.today() - relativedelta(months=months))
            .strftime('%m.%y')
        )

    @staticmethod
    def _energomera_prev_day(match):
        """
        Static method to calculate previous day in meter's format.

        :return: Previous day formatted as ``<day number>.<month
          number>.<year>``
        :rtype: str
        """
        days = EnergomeraConfig._energomera_re_expr_param_int(match, 1)
        return (
            (date.today() - relativedelta(days=days))
            .strftime('%d.%m.%y')
        )

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
        return Schema({
            Optional('general', default=DEFAULT_CONFIG.general): Schema({
                # Re-use defaults from `general_defaults`
                Optional('oneshot',
                         default=DEFAULT_CONFIG.general.oneshot): bool,
                Optional('intercycle_delay',
                         default=DEFAULT_CONFIG.general.intercycle_delay): int,
                Optional('logging_level',
                         default=DEFAULT_CONFIG.general.logging_level): And(
                    str,
                    lambda x: x in self._logging_levels,
                    error='Invalid logging level - should be one of'
                          f' {", ".join(self._logging_levels.keys())}'
                ),
                Optional(
                    'include_default_parameters',
                    default=DEFAULT_CONFIG.general.include_default_parameters
                ): bool,
            }),
            'meter': {
                'port': str,
                'password': str,
                Optional('timeout', default=DEFAULT_CONFIG.meter.timeout): int,
            },
            'mqtt': {
                'host': str,
                Optional('user', default=None): str,
                Optional('password', default=None): str,
                Optional('hass_discovery_prefix',
                         default='homeassistant'): str,
                Optional('tls', default=True): bool,
            },
            Optional('parameters', default=DEFAULT_CONFIG.parameters): [
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

    @staticmethod
    def _read_config(config_file):
        """
        Reads configuration file.

        :param str config_file: Name of configuration file
        :return str: Configuration file contents
        """
        with open(config_file, encoding='ascii') as file:
            content = file.read()

        return content

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
                content = self._read_config(config_file)

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
        # chained) attributes is available
        self._config = Dict(config)
        # If enabled makes parameters a combination of default ones plus those
        # defined in the configuration file, no check for duplicates is
        # performed!
        if self._config.general.include_default_parameters:
            self._config.parameters = (
                DEFAULT_CONFIG.parameters + self._config.parameters
            )
        # Make a copy of the original configuration for the `interpolate()`
        # method to access initially defined interpolation expressions if any
        self._orig_config = deepcopy(self._config)

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
        Returns logging level suitable for :mod:`logging` library

        :return: Logging level
        :rtype: int
        """

        return self._logging_levels.get(self._config.general.logging_level)

    def interpolate(self):
        """
        Interpolates certain expressions in ``parameters`` section of the
        configuration. The method uses original configuration as read from the
        source, to access expressions to interpolate.

        Supported expressions:

        - ``{{ energomera_prev_month }}``: Previous month in meter's format
        - ``{{ energomera_prev_day }}``: Previous day in meter's format
        """
        # Iterate over the original configuration
        for idx, param in enumerate(self._orig_config.parameters):
            for key, value in param.items():
                # Interpolate expressions in string values
                if isinstance(value, str):
                    value = re.sub(r'{{\s*energomera_prev_month\s*(.*?)\s*}}',
                                   self._energomera_prev_month, value)
                    value = re.sub(r'{{\s*energomera_prev_day\s*(.*?)\s*}}',
                                   self._energomera_prev_day, value)
                    # Store the (possibly) interpolated value to the
                    # configuration exposed to the consumers
                    self._config.parameters[idx][key] = value
