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
Package provide single HASS sensor over MQTT from energy meter read using IEC
protocol.
"""
from __future__ import annotations
from typing import (
    Dict, TYPE_CHECKING, Optional, Union, Collection, List
)
import json
import logging
if TYPE_CHECKING:
    from .schema import ConfigMqttSchema, ConfigParameterSchema
    from .mqtt_client import MqttClient
    from iec62056_21.messages import DataSet as IecDataSet

_LOGGER = logging.getLogger(__name__)


class IecToHassSensor:  # pylint: disable=too-many-instance-attributes
    """
    Processes entity received from the meter IEC 62056-21 protocol in
    accordance with given configuration from the ``parameters`` section and
    sends them over to HomeAssistant using MQTT.

    :param mqtt_config: ``mqtt`` fragment of the configuration
    :param mqtt_client: Instance of MQTT client
    :param config_param: particular entry from ``parameters``
     configuration section
    :param iec_item: Entry received from
     the meter for the specified ``config_param``
    """

    # Class attribute to store HASS sensors having config payload sent, to
    # ensure it is done only once per multiple instantiations of the class -
    # HASS needs sensor discovery only once, otherwise logs a message re:
    # sensor has already been discovered
    hass_config_payloads_published: Dict[str, int] = {}
    # Class attribute defining MQTT topic base for HASS discovery
    _mqtt_topic_base = 'sensor'

    def __init__(  # pylint: disable=too-many-arguments
        self, mqtt_config: ConfigMqttSchema, mqtt_client: MqttClient,
        config_param: ConfigParameterSchema, iec_item: List[IecDataSet],
        model: str, sw_version: str, serial_number: str
    ) -> None:
        self._config_param = config_param
        self._iec_item = iec_item
        self._mqtt_config = mqtt_config
        self._mqtt_client = mqtt_client
        self._hass_item_name: Optional[str] = None
        self._hass_device_id: Optional[str] = None
        self._hass_unique_id: Optional[str] = None
        self._hass_config_topic: Optional[str] = None
        self._hass_state_topic: Optional[str] = None
        self._model = model
        self._sw_version = sw_version
        self._serial_number = serial_number

    @property
    def state_last_will_payload(self) -> Optional[str]:
        """
        Stores value of last will payload to be set for MQTT client.

        Should be implemented by subclasses.
        """
        return None

    @property
    def iec_item(self) -> List[IecDataSet]:
        """
        Provides IEC entity associated with the instance.

        :return: IEC entity
        """
        return self._iec_item

    @iec_item.setter
    def iec_item(self, value: List[IecDataSet]) -> None:
        """
        Sets IEC entity associated with the instance.

        :param value: IEC entity
        """
        self._iec_item = value

    def iec_try_value_by_index(self) -> None:
        """
        Attempts to pick an item from multi-valued meter's response (if
        ``response_idx`` is configured in the entry of `parameters` section
        being processed).
        """
        if self._config_param.response_idx is not None:
            try:
                self.iec_item = [
                    self.iec_item[self._config_param.response_idx]
                ]
            except IndexError:
                _LOGGER.error("Response for IEC entry at '%s' doesn't"
                              " contain element at index '%s', skipping.\n"
                              "Response: '%s'",
                              self._config_param.address,
                              self._config_param.response_idx, self.iec_item)
                self.iec_item = []

    def hass_gen_hass_sensor_props(self, idx: int) -> None:
        """
        Generates various properties for the HASS sensor (device and unique
        IDs, MQTT topic names etc.).
        """
        self._hass_device_id = f'{self._model}_{self._serial_number}'
        self._hass_unique_id = f'{self._hass_device_id}' \
            f'_{self._config_param.entity_name or self._config_param.address}'

        if isinstance(self._config_param.name, list):
            self._hass_item_name = self._config_param.name[0]
        else:
            self._hass_item_name = self._config_param.name

        # Multiple addresses with likely same name, the caller has to
        # provide meaningful names for those anyways even if they are
        # different by a reason
        if len(self.iec_item) > 1:
            self._hass_unique_id += f'_{idx}'
            # Pick next name if a list has been provided
            if isinstance(self._config_param.name, list):
                try:
                    self._hass_item_name = self._config_param.name[idx]
                except IndexError:
                    # Fallback to address + index if name at entry index
                    # doesn't exist
                    self._hass_item_name = (
                        f'{self._config_param.address} {idx}'
                    )
            # Otherwise append the item index to make name unique
            else:
                self._hass_item_name += f' {idx}'

        # Compose base element of MQTT topics
        topic_base_parts = [
            self._mqtt_topic_base,
            self._hass_device_id, self._hass_unique_id,
        ]
        if self._mqtt_config.hass_discovery_prefix:
            topic_base_parts.insert(
                0, self._mqtt_config.hass_discovery_prefix
            )
        topic_base = '/'.join(topic_base_parts)

        # Config and state MQTT topics for HomeAssistant discovery, see
        # https://www.home-assistant.io/docs/mqtt/discovery/ for details
        self._hass_config_topic = f'{topic_base}/config'
        self._hass_state_topic = f'{topic_base}/state'

    def hass_config_payload(
        self
    ) -> Dict[str, Union[str, Collection[str], Dict[str, str]]]:
        """
        Returns HASS config payload for the item.

        :return: HASS config payload
        """
        # Normally `set_hass_gen_hass_sensor_props` will ensure these are
        # defined, but their types are `Optional` hence the check to ensure
        # typing validations pass
        assert (
            self._hass_item_name and self._hass_device_id
            and self._hass_unique_id and self._hass_state_topic
        ), 'HASS item properties are missing'

        res = dict(
            name=self._hass_item_name,
            device=dict(
                name=self._serial_number,
                ids=self._hass_device_id,
                model=self._model,
                sw_version=self._sw_version,
            ),
            device_class=self._config_param.device_class,
            unique_id=self._hass_unique_id,
            object_id=self._hass_unique_id,
            unit_of_measurement=self._config_param.unit,
            state_class=self._config_param.state_class,
            state_topic=self._hass_state_topic,
            value_template='{{ value_json.value }}',
        )
        # Skip empty values
        return {k: v for k, v in res.items() if v is not None}

    def hass_state_payload(  # pylint: disable=no-self-use
        self, value: str
    ) -> Dict[str, str]:
        """
        Returns HASS state payload for the item.

        :return: HASS state payload
        """
        return dict(
            value=value
        )

    async def process(self, setup_only: bool = False) -> None:
        """
        Processes the entry received from the meter and sends it to HASS over
        MQTT.

        :param setup_only: Perform only setup steps for the entiry, such
         as determining MQTT topics etc., with no payloads sent to MQTT. Used
         to configure MQTT last will, since it has to be done prior to
         connecting to MQTT broker, thus no payloads could be sent yet
        """
        _LOGGER.debug("Processing entry: IEC address '%s',"
                      " additional data '%s', index in response '%s';"
                      " HASS name '%s', entity name '%s'",
                      self._config_param.address,
                      self._config_param.additional_data,
                      self._config_param.response_idx, self._config_param.name,
                      self._config_param.entity_name)

        self.iec_try_value_by_index()
        for idx, iec_value in enumerate(self.iec_item):
            try:
                self.hass_gen_hass_sensor_props(idx)
                _LOGGER.debug("Using '%s' as HASS name for IEC enttity"
                              " at '%s' address",
                              self._hass_item_name, self._config_param.address)
                # Set last will for MQTT if specified for the item
                if self.state_last_will_payload is not None:
                    will_payload = self.hass_state_payload(
                        value=self.state_last_will_payload
                    )
                    json_will_payload = json.dumps(will_payload)

                    self._mqtt_client.will_set(
                        topic=self._hass_state_topic,
                        payload=json_will_payload
                    )

                    _LOGGER.debug(
                        "Set HASS state topic for MQTT last will,"
                        " payload: '%s'",
                        json_will_payload
                    )

                # Skip sending MQTT payloads if only setup steps have been
                # requested
                if setup_only:
                    continue

                # Ensure HASS unique ID and config topic are defined, normally
                # `set_hass_gen_hass_sensor_props` will set these, while their
                # `Optional` type will result in typying validation error if
                # not checked
                assert self._hass_unique_id, 'HASS unique ID is missing'
                assert self._hass_config_topic, 'HASS config topic is missing'
                assert self._hass_state_topic, 'HASS state topic is missing'
                # Send configuration payloads using MQTT once per sensor
                config_payload = self.hass_config_payload()
                json_config_payload = json.dumps(config_payload)
                config_payload_sent_hash = (
                    self.hass_config_payloads_published.get(
                        self._hass_unique_id, None
                    )
                )
                # (re)send the configuration payload once it changes (e.g. due
                # to interpolation)
                if config_payload_sent_hash != hash(json_config_payload):
                    _LOGGER.debug("MQTT config payload for HASS"
                                  " auto-discovery: '%s'",
                                  json_config_payload)

                    await self._mqtt_client.publish(
                        topic=self._hass_config_topic,
                        payload=json_config_payload,
                        retain=True,
                    )
                    # Keep track of JSON formatted configuration payloads sent
                    self.hass_config_payloads_published[
                        self._hass_unique_id
                    ] = hash(json_config_payload)

                    _LOGGER.debug("Sent HASS config payload to MQTT topic"
                                  " '%s'",
                                  self._hass_config_topic)

                # Sensor state payload
                state_payload = self.hass_state_payload(
                    value=iec_value.value
                )
                json_state_payload = json.dumps(state_payload)
                _LOGGER.debug("MQTT state payload for HASS auto-discovery:"
                              " '%s'",
                              json_state_payload)

                # Send sensor state
                await self._mqtt_client.publish(
                    topic=self._hass_state_topic,
                    payload=json_state_payload
                )
                _LOGGER.debug("Sent HASS state payload to MQTT topic '%s'",
                              self._hass_state_topic)

            # pylint: disable=broad-except
            except Exception as exc:
                _LOGGER.error('Got following exception while processing'
                              ' entity at address %s (index %s),'
                              " skipping to next.\n"
                              " Configuration parameters: %s\n"
                              ' Exception: %s',
                              self._config_param.address, idx,
                              self._config_param, exc, exc_info=True)
                continue
