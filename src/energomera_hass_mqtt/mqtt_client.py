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
The package provides additional functionality over `aiomqtt`.
"""
import logging
import aiomqtt

_LOGGER = logging.getLogger(__name__)


class MqttClient(aiomqtt.Client):
    """
    The class extends the `aiomqtt.Client` to provide better convenience
    working with last wills. Namely, the original class only allows setting the
    last will thru its constructor, while the `EnergomeraHassMqtt` consuming it
    only has required property for that around actual publish calls.

    :param args: Pass-through positional arguments for parent class
    :param kwargs: Pass-through keyword arguments for parent class
    """
    def __init__(self, *args, **kwargs):
        self._will_set = 'will' in kwargs
        super().__init__(logger=_LOGGER, *args, **kwargs)

    async def connect(self):
        """
        Connects to MQTT broker using `__aenter__` method of the base class as
        recommended in
        https://github.com/sbtinstruments/aiomqtt/blob/main/docs/migration-guide-v2.md.
        Multiple calls will result only in single call to `__aenter__()` method
        of parent class if the MQTT client needs a connection (not being
        connected or got disconnected), to allow the method to be called within
        a process loop with no risk of hitting non-reentrant error from base
        class.
        """
        # Using combination of `self._connected` and `self._disconnected` (both
        # inherited from `asyncio_mqtt.client`) to detect of MQTT client needs
        # a reconnection upon a network error isn't reliable - the former isn't
        # finished even after a disconnect, while the latter stays with
        # exception after a successfull reconnect. Neither
        # `self._client.is_connected` (from Paho client) is - is returns True
        # if socket is disconnected due to network error. Only testing for
        # `self._client.socket()` (from Paho client as well) fits the purpose -
        # None indicates the client needs `connect`
        if self._client.socket():
            _LOGGER.debug(
                'MQTT client is already connected, skipping subsequent attempt'
            )
            return

        # Disconnected client could still hold its lock, release it first
        await self.disconnect()

        # And then connect
        # pylint:disable=unnecessary-dunder-call
        await self.__aenter__()

    async def disconnect(self):
        """
        Disconnects from MQTT broker using `__aexit__` method of the base class
        as per migration guide above.
        """
        # pylint:disable=unnecessary-dunder-call
        await self.__aexit__(None, None, None)

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
