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
from __future__ import annotations
from typing import Optional, cast
from datetime import date
from copy import deepcopy
import re
from re import Match
from dateutil.relativedelta import relativedelta
import yaml
from pydantic import ValidationError
from .schema import ConfigSchema, ConfigParameterSchema
from .const import DEFAULT_CONFIG_PARAMETERS, LOGGING_LEVELS
from .exceptions import EnergomeraConfigError


class EnergomeraConfig:
    """
    Class representing configuration for :class:`EnergomeraHassMqtt` one.

    :param config_file: Name of configuration file
    :param content: Literal content representing the configuration
    """

    @staticmethod
    def _energomera_re_expr_param_int(
        match: Match[str], default: int
    ) -> int:
        """
        Static method to be used with ``re.sub()`` as callable processing the
        first match group as the argument to interpolation expression.

        :param match: Match object provided by ``re.sub``
        :param default: Default value for the argument
        :return: Interpolated value for the expression argument
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
    def _energomera_prev_month(match: Match[str]) -> str:
        """
        Static method to calculate previous month in meter's format.

        :return: Previous month formatted as ``<month number>.<year>``
        """

        months = EnergomeraConfig._energomera_re_expr_param_int(match, 1)
        return (
            (date.today() - relativedelta(months=months))
            .strftime('%m.%y')
        )

    @staticmethod
    def _energomera_prev_day(match: Match[str]) -> str:
        """
        Static method to calculate previous day in meter's format.

        :return: Previous day formatted as ``<day number>.<month
          number>.<year>``
        """
        days = EnergomeraConfig._energomera_re_expr_param_int(match, 1)
        return (
            (date.today() - relativedelta(days=days))
            .strftime('%d.%m.%y')
        )

    @staticmethod
    def _read_config(config_file: str) -> str:
        """
        Reads configuration file.

        :param config_file: Name of configuration file
        :return: Configuration file contents
        """
        with open(config_file, encoding='ascii') as file:
            content = file.read()

        return content

    def __init__(
        self, config_file: Optional[str] = None, content: Optional[str] = None
    ) -> None:
        """
        Initializes configuration state either from file or content string.

        :param config_file: Name of configuration file
        :param content: Configuration contents
        """
        if not config_file and not content:
            raise EnergomeraConfigError(
                "Either 'config_file' or 'content' should be provided"
            )

        try:
            if not content:
                # Cast the configure file name, since the check above ensures
                # it is defined
                content = self._read_config(cast(str, config_file))

            config = yaml.safe_load(content)
        except (yaml.YAMLError, OSError) as exc:
            raise EnergomeraConfigError(
                f'Error loading configuration file:\n{str(exc)}'
            ) from None

        try:
            config = ConfigSchema.model_validate(config)
        except ValidationError as exc:
            errors = [
                f"{'.'.join([str(y) for y in x['loc']])}: {x['msg']}"
                for x in exc.errors()
            ]
            raise EnergomeraConfigError(
                'Error validating configuration file:\n' + '\n'.join(errors)
            ) from None

        self._config: ConfigSchema = config
        # If enabled makes parameters a combination of default ones plus those
        # defined in the configuration file, no check for duplicates is
        # performed!
        if self._config.general.include_default_parameters:
            self._config.parameters = (
                [
                    ConfigParameterSchema.model_validate(x)
                    for x in DEFAULT_CONFIG_PARAMETERS
                ] + self._config.parameters
            )
        # Make a copy of the original configuration for the `interpolate()`
        # method to access initially defined interpolation expressions if any
        self._orig_config = deepcopy(self._config)

    @property
    def of(self) -> ConfigSchema:
        """
        Returns the configuration state

        :return: Configuration state
        """
        return self._config

    @property
    def logging_level(self) -> int:
        """
        Returns logging level suitable for :mod:`logging` library

        :return: Logging level
        """

        return LOGGING_LEVELS[self._config.general.logging_level]

    def interpolate(self) -> None:
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
            for key, value in param.model_dump().items():
                # Interpolate expressions in string values
                if isinstance(value, str):
                    value = re.sub(r'{{\s*energomera_prev_month\s*(.*?)\s*}}',
                                   self._energomera_prev_month, value)
                    value = re.sub(r'{{\s*energomera_prev_day\s*(.*?)\s*}}',
                                   self._energomera_prev_day, value)
                    # Store the (possibly) interpolated value to the
                    # configuration exposed to the consumers
                    setattr(self._config.parameters[idx], key, value)

    def __repr__(self) -> str:
        """
        Returns string representation of the configuration.

        :return: String representation
        """
        res = ''
        for section in ('general', 'meter', 'mqtt'):
            res += f' - {section}: ' + ', '.join([
                f'{k}={v}' for k, v
                in getattr(
                    self._config, section
                ).model_dump(exclude_none=True).items()
            ]) + '\n'
        res += f' - parameters: count={len(self._config.parameters)}\n'
        return res
