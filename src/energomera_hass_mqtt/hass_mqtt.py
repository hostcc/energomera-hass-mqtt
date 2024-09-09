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
Package to read data from Energomera energy meter and send over to
HomeAssistant using MQTT.
"""
from __future__ import annotations
from typing import Optional, TYPE_CHECKING, cast, List
import logging
import ssl
from os import getenv
from time import time

from iec62056_21.messages import CommandMessage, DataSet as IecDataSet
from iec62056_21.client import Iec6205621Client
from iec62056_21.transports import SerialTransport
from iec62056_21 import utils
from .mqtt_client import MqttClient
from .iec_hass_sensor import IecToHassSensor
from .extra_sensors import PseudoBinarySensor, PseudoSensor
from .schema import ConfigParameterSchema
from .exceptions import EnergomeraMeterError
if TYPE_CHECKING:
    from .config import EnergomeraConfig

_LOGGER = logging.getLogger(__name__)


# pylint: disable=too-many-instance-attributes
class EnergomeraHassMqtt:
    """
    Communicates with Energomera energy meters using IEC 62056-21 (supersedes
    IEC 61107) and sends values of requested parameters to HomeAssisstant using
    MQTT.

    :param config: Configuration state
    """

    @staticmethod
    def calculate_bcc(bytes_data: bytes) -> bytes:
        """
        Calculates protocol BCC using Energomera non-standard modification of
        IEC 1155-78.

        See http://www.energomera.ru/documentations/product/ce301_303_rp.pdf,
        page 126, for more details.

        :param bytes_data: The data to calculate BCC over
        :return: Calculated BCC
        """
        bcc = 0
        for elem in bytes_data:
            bcc += elem
            bcc = bcc & 0xFF
        bcc = bcc & 0x7F
        return bcc.to_bytes(length=1, byteorder='big')

    def __init__(
        self, config: EnergomeraConfig,
    ):
        self._config = config
        # Override the method in the `iec62056_21` library with the specific
        # implementation
        # pylint: disable=protected-access
        utils._calculate_bcc = EnergomeraHassMqtt.calculate_bcc

        # Currently `Iec6205621Client.with_serial_transport()` method doesn't
        # accept timeout, so instantiate the IEC client with explicit transport
        # - its constructor _does_ accept it
        self._client = Iec6205621Client(
            password=config.of.meter.password.get_secret_value(),
            transport=SerialTransport(
                port=config.of.meter.port,
                timeout=config.of.meter.timeout
            )
        )

        mqtt_tls_context = None
        if config.of.mqtt.tls:
            _LOGGER.debug('Enabling TLS for MQTT connection')
            # Required for TLS-enabled MQTT broker
            mqtt_tls_context = ssl.SSLContext()

        self._mqtt_client = MqttClient(
            hostname=getenv('MQTT_HOST', config.of.mqtt.host),
            port=getenv('MQTT_PORT', config.of.mqtt.port),
            username=getenv('MQTT_USER', config.of.mqtt.user),
            password=getenv(
                'MQTT_PASSWORD',
                (
                    config.of.mqtt.password.get_secret_value()
                    if config.of.mqtt.password else None
                )
            ),
            tls_context=mqtt_tls_context,
            # Set MQTT keepalive to interval between meter interaction cycles,
            # so that MQTT broker will consider the client disconnected upon
            # that internal if no MQTT traffic is seen from the client.
            # Please note the interval could be shorter due to the use of
            # `asyncio_mqtt`, since its asynchrounous task runs in the loop and
            # can respond to MQTT pings anytime in between meter cycles.
            keepalive=config.of.general.intercycle_delay,
        )
        self._hass_discovery_prefix = config.of.mqtt.hass_discovery_prefix
        self._model = None
        self._serial_number = None
        self._sw_version = None

        # (re)initialize what configuration payloads have been sent across all
        # instances of `IecToHassSensor`. Mostly used by tests, as
        # `async_main()` instantiates the class only once
        IecToHassSensor.hass_config_payloads_published = {}

    def iec_read_values(
        self, address: str, additional_data: Optional[str] = None
    ) -> List[IecDataSet]:
        """
        Reads value(s) at selected address from the meter using IEC 62056-21
        protocol.

        :param address: Address of meter parameter to read
        :param additional_data: Additional data to read the parameter with
         (argument to parameter's address)
        :return: Parameter's data received from the meter
        """
        request = CommandMessage.for_single_read(
            address, additional_data
        )
        self._client.transport.send(request.to_bytes())

        # `iec62056_21` library doesn't provide typiing hints for the response,
        # so cast it explicitly
        return cast(List[IecDataSet], self._client.read_response().data)

    def set_meter_ids(self, hello_response: List[IecDataSet]) -> None:
        """
        Stores meter's model, serial number and software version.

        :param hello_response: Response to 'HELLO' command
        """
        if len(hello_response) != 1:
            raise ValueError(
                'Failed to retrieve meter identification data'
            )
        [_, self._model, self._sw_version, self._serial_number, _
         ] = hello_response[0].value.split(',')

        _LOGGER.debug(
            "Retrieved identification data from meter:"
            " model '%s', SW version '%s', serial number: '%s'",
            self._model, self._sw_version, self._serial_number
        )
        if not all([self._model, self._sw_version, self._serial_number]):
            raise EnergomeraMeterError(
                'Failed to retrieve meter identification data'
            )

    async def iec_read_admin(self) -> None:
        """
        Primary method to loop over the parameters requested and process them.
        """

        start = time()
        try:
            _LOGGER.debug('Opening connection with meter')
            self._client.connect()
            self._client.startup()
            # Start the session in programming mode since it is faster one, as
            # it switches to baud rate higher than initial (300 baud, as per
            # IEC 62056-21, mode C). Requires password to be provided when
            # constructing the instance of the class
            _LOGGER.debug('Entering programming mode with meter')
            self._client.ack_with_option_select("programming")
            self._client.read_response()
            self._client.send_password()
            self._client.read_response()

            # Read meter identification (mode, SW version, serial number)
            self.set_meter_ids(self.iec_read_values('HELLO'))

            # This call will set last will only, which has to be done prior to
            # connecting to the broker
            await self.set_online_sensor(False, setup_only=True)
            # The connection to MQTT broker is instantiated only once, if not
            # connected previously.
            await self._mqtt_client.connect()
            # Process parameters requested
            for param in self._config.of.parameters:
                iec_item = self.iec_read_values(
                    param.address, param.additional_data
                )

                hass_item = IecToHassSensor(
                    mqtt_config=self._config.of.mqtt,
                    mqtt_client=self._mqtt_client, config_param=param,
                    iec_item=iec_item,
                    # `set_meter_ids()` ensures these values are defined, so
                    # cast them dropping `Optional` type
                    model=cast(str, self._model),
                    sw_version=cast(str, self._sw_version),
                    serial_number=cast(str, self._serial_number)
                )
                await hass_item.process()

            # End the session
            _LOGGER.debug('Closing session with meter')
            self._client.send_break()
        except TimeoutError as exc:
            await self.set_online_sensor(False)
            raise exc
        else:
            await self.set_online_sensor(True)
            duration = time() - start
            await self.set_duration_sensor(duration)
        finally:
            # Disconnect serial client ignoring possible
            # exceptions - it might have not been connected yet
            try:
                self._client.disconnect()
            except Exception:  # pylint: disable=broad-except
                pass

    async def finalize(self) -> None:
        """
        Performs finalization steps, that is - disconnecting MQTT client
        currently.
        """
        try:
            await self.set_online_sensor(False)
            await self._mqtt_client.disconnect()
        except Exception:  # pylint: disable=broad-except
            pass

    async def set_online_sensor(
        self, state: bool, setup_only: bool = False
    ) -> None:
        """
        Adds a pseudo-sensor to HASS reflecting the communication state of
        meter - online or offline.

        :param state: The sensor state
        """
        # The variables normally are ensured by `set_meter_ids()`
        # method, but the types of the variables are still `Optional` hence the
        # check
        assert (
            self._model and self._sw_version and self._serial_number
        ), 'Meter identification data is missing'

        # Add a pseudo-sensor
        param = ConfigParameterSchema(
            address='IS_ONLINE',
            name='Meter online status',
            device_class='connectivity',
            additional_data=None,
            response_idx=None,
            entity_name=None,
        )
        hass_item = PseudoBinarySensor(
            mqtt_config=self._config.of.mqtt,
            mqtt_client=self._mqtt_client, config_param=param,
            value=state, model=self._model, sw_version=self._sw_version,
            serial_number=self._serial_number
        )
        # Set the last will of the MQTT client to the `state=False`
        hass_item.state_last_will_payload = False
        await hass_item.process(setup_only)

    async def set_duration_sensor(self, value: float) -> None:
        """
        Adds a pseudo-sensor to HASS reflecting the duration of the meter
        cycle.
        """
        _LOGGER.debug('Cycle duration: %s s', value)
        # Add a pseudo-sensor
        param = ConfigParameterSchema(
            address='CYCLE_DURATION',
            name='Meter cycle duration',
            unit='s',
            entity_category='diagnostic',
        )
        hass_item = PseudoSensor[float](
            mqtt_config=self._config.of.mqtt,
            mqtt_client=self._mqtt_client, config_param=param,
            value=value, model=self._model, sw_version=self._sw_version,
            serial_number=self._serial_number
        )
        await hass_item.process()
