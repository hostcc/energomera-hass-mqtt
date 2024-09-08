# Copyright (c) 2023 Ilia Sotnikov
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
Package to provide additional sensors on top of `IecToHassSensor`.
"""
from __future__ import annotations
from typing import Dict, Union, Any
import logging
from .iec_hass_sensor import IecToHassSensor

_LOGGER = logging.getLogger(__name__)


class IecToHassBinarySensor(IecToHassSensor):
    """
    Represents HASS binary sensor.
    """
    _mqtt_topic_base = 'binary_sensor'

    def hass_state_payload(
        self, value: Union[str, str]
    ) -> Dict[str, str]:  # pylint: disable=no-self-use
        """
        Transforms the binary sensor payload to the format understood by HASS
        MQTT discovery for the sensor type.

        :param value: The sensor value
        """
        if isinstance(value, bool):
            b_value = value
        elif isinstance(value, str):
            b_value = value.lower() == 'true'
        else:
            raise TypeError(
                f'Unsupported argument type to {__name__}: {type(value)}'
            )

        return dict(
            value='ON' if b_value else 'OFF'
        )


class PseudoBinarySensor(IecToHassBinarySensor):
    """
    Represents a pseudo-sensor, i.e. one doesn't exist on meter.

    :param value: The sensor value
    :param args: Parameters passed through to parent constructor
    :param kwargs: Keyword parameters passed through to parent constructor
    """
    def __init__(self, value: bool, *args: Any, **kwargs: Any):
        class PseudoValue:  # pylint: disable=too-few-public-methods
            """
            Mimics `class`:iec62056_21.messages.AnswerDataMessage to store the
            sensor value in a conmpatible manner.

            :param value: Sensor value
            """
            value = None

            def __init__(self, value: bool) -> None:
                self.value = value

        # Invoke the parent constructor providing `iec_item` from the
        # pseudo-sensor value
        kwargs['iec_item'] = [PseudoValue(value)]
        super().__init__(*args, **kwargs)
