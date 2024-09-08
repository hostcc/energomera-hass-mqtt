# Copyright (c) 2024 Ilia Sotnikov
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
Module containing configuration file schema.
"""
from __future__ import annotations
from typing import Optional, List, Union
from pydantic import (
    BaseModel, field_validator, SecretStr, model_validator
)
from .const import (
    DEFAULT_CONFIG_GENERAL_INCLUDE_DEFAULT_PARAMETERS,
    DEFAULT_CONFIG_GENERAL_INTERCYCLE_DELAY,
    DEFAULT_CONFIG_GENERAL_LOGGING_LEVEL, DEFAULT_CONFIG_GENERAL_ONESHOT,
    DEFAULT_CONFIG_METER_TIMEOUT, DEFAULT_CONFIG_MQTT_PORT,
    DEFAULT_CONFIG_GENERAL, LOGGING_LEVELS
)


class ConfigGeneralSchema(BaseModel):
    """
    Class representing configuration schema for general settings.
    """
    oneshot: bool = DEFAULT_CONFIG_GENERAL_ONESHOT
    intercycle_delay: int = DEFAULT_CONFIG_GENERAL_INTERCYCLE_DELAY
    logging_level: str = DEFAULT_CONFIG_GENERAL_LOGGING_LEVEL
    include_default_parameters: bool = (
        DEFAULT_CONFIG_GENERAL_INCLUDE_DEFAULT_PARAMETERS
    )

    @field_validator('logging_level', mode='after')
    @classmethod
    def validate_logging_level(cls, value: str) -> str:
        """
        Validates logging level.
        """
        valid_levels = LOGGING_LEVELS.keys()
        if value not in valid_levels:
            valid_levels_str = ', '.join([f"'{x}'" for x in valid_levels])
            raise ValueError(
                f'should be one of {valid_levels_str}'
            )

        return value


class ConfigMeterSchema(BaseModel):
    """
    Class representing configuration schema for meter connection.
    """
    port: str
    password: SecretStr
    timeout: int = DEFAULT_CONFIG_METER_TIMEOUT


class ConfigMqttSchema(BaseModel):
    """
    Class representing configuration schema for MQTT connection.
    """
    host: str
    port: int = DEFAULT_CONFIG_MQTT_PORT
    user: Optional[str] = None
    password: Optional[SecretStr] = None
    hass_discovery_prefix: str = 'homeassistant'
    tls: bool = True


class ConfigParameterSchema(BaseModel):
    """
    Class representing configuration schema for a single parameter.
    """
    address: str
    name: Union[str, List[str]]
    device_class: str
    state_class: Optional[str] = None
    unit: Optional[str] = None
    additional_data: Optional[str] = None
    entity_name: Optional[str] = None
    response_idx: Optional[int] = None


class ConfigSchema(BaseModel):
    """
    Class representing configuration schema.
    """
    # Whole `general` section could be skipped, as it is provided with the
    # defaults below
    general: ConfigGeneralSchema = (
        ConfigGeneralSchema.model_validate(DEFAULT_CONFIG_GENERAL)
    )
    meter: ConfigMeterSchema
    mqtt: ConfigMqttSchema
    parameters: List[ConfigParameterSchema] = []

    @model_validator(mode='after')
    def validate_parameters(self: ConfigSchema) -> ConfigSchema:
        """
        Validates `parameters` section.
        """
        if (
            not self.parameters
            and not self.general.include_default_parameters
        ):
            raise ValueError(
                "'parameters' should not be empty if"
                " 'general.include_default_parameters' is not enabled"
            )

        return self
