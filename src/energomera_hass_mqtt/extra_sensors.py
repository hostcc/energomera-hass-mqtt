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
from typing import Any, Generic, TypeVar, Optional
from iec62056_21.messages import DataSet as IecDataSet
from .iec_hass_sensor import IecToHassSensor

T = TypeVar('T')


class PseudoSensor(IecToHassSensor, Generic[T]):
    """
    Represents a pseudo-sensor, i.e. one doesn't exist on meter.
    """
    def __init__(self, value: T, *args: Any, **kwargs: Any):
        self._state_last_will_payload: Optional[T] = None
        # Invoke the parent constructor providing `iec_item` from the
        # pseudo-sensor value
        kwargs['iec_item'] = [
            IecDataSet(value=PseudoSensor._format_value(value))
        ]
        super().__init__(*args, **kwargs)

    @staticmethod
    def _format_value(value: T) -> Optional[str]:
        """
        Formats the sensor's value according to its type.

        :param value: The sensor value
        :return: The formatted value
        """
        result = None
        if isinstance(value, bool):
            result = 'ON' if value else 'OFF'
        else:
            result = str(value)
        return result

    @property
    def state_last_will_payload(self) -> Optional[str]:
        """
        Stores the value of the last will payload for the item, i.e. sent by
        the MQTT broker if the client disconnects uncleanly.

        :param value: Value for last will payload
        """
        return PseudoSensor._format_value(self._state_last_will_payload)

    @state_last_will_payload.setter
    def state_last_will_payload(self, value: T) -> None:
        self._state_last_will_payload = value


class PseudoBinarySensor(PseudoSensor[bool]):
    """
    Represents a binary pseudo-sensor.
    """
    _mqtt_topic_base = 'binary_sensor'
