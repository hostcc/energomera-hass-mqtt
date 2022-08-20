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
The package provides additional functionality over `asyncio_mqtt`.
"""
import logging
import asyncio_mqtt

_LOGGER = logging.getLogger(__name__)


class MqttClient(asyncio_mqtt.Client):
    """
    Class attribute allowing to provide MQTT keepalive down to MQTT client.
    Used only by tests at the moment, thus no interface controlling the
    attribute is provided.
    """
    _keepalive = None
    """
    The class extends the `asyncio_mqtt.Client` to provide better convenience
    working with last wills. Namely, the original class only allows setting the
    last will thru its constructor, while the `EnergomeraHassMqtt` consuming it
    only has required property for that around actual publish calls.

    :param args: Pass-through positional arguments for parent class
    :param kwargs: Pass-through keyword arguments for parent class
    """
    def __init__(self, *args, **kwargs):
        self._will_set = 'will' in kwargs
        # Pass keepalive option down to parent class if set
        if self._keepalive:
            kwargs['keepalive'] = self._keepalive
        super().__init__(logger=_LOGGER, *args, **kwargs)

    def will_set(self, *args, **kwargs):
        """
        Allows setting last will to the underlying MQTT client.

        Skips updating the last will if one has already been set (either via
        the method or through the constructor).

        :param args: Pass-through positional arguments for parent method
        :param kwargs: Pass-through keyword arguments for parent method
        """
        if self._will_set:
            return
        self._client.will_set(*args, **kwargs)
        self._will_set = True

    def will_clear(self):
        """
        Clears the last will might have been set previously.
        """
        self._client.will_clear()
        self._will_set = False
