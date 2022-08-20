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

'''
Tests for online sensor behavior
'''
import os
import shutil
import tempfile
import asyncio
import time
import json
from unittest.mock import patch, call
import docker
import pytest
from test_energomera import mock_serial, mock_mqtt, mock_config
from energomera_hass_mqtt.mqtt_client import MqttClient
from energomera_hass_mqtt.main import async_main, main


# pylint: disable=too-few-public-methods
class MqttClientTimedSubscribe(MqttClient):
    '''
    MQTT client with timed subscribe functionality - that is, allowing to
    received messages from subscription within configured time frame. The
    existing MQTT client, in contrast, awaits for the messages indefinitely

    :param int subscribe_timeout: Time interval to wait for messages coming
     from MQTT subscription
    :param list *args: Pass through positional arguments
    :param dict *kwargs: Pass trhough keyword arguments
    '''
    def __init__(self, subscribe_timeout, *args, **kwargs):
        self._subscribe_timeout = subscribe_timeout
        super().__init__(*args, **kwargs)

    def _cb_and_generator(self, *_args, **_kwargs):
        '''
        Overrides the method providing callback for messages received from
        subscription and sending them to the caller from async generator.
        '''
        messages = asyncio.Queue()

        def _put_in_queue(_client, _userdata, msg):
            '''
            MQTT callback that simply puts received messages to the queue
            '''
            messages.put_nowait(msg)

        async def _generator():
            '''
            Asynchronous generator that sends messages from the queue received
            within configured time interval
            '''
            try:
                asyncio_create_task = asyncio.create_task
            except AttributeError:
                # Python 3.6 has no `asyncio.create_task`
                asyncio_create_task = asyncio.ensure_future

            while True:
                task = asyncio_create_task(messages.get())
                done, _ = await asyncio.wait(
                    [task], timeout=self._subscribe_timeout
                )
                # Stop processing messages if configured internal has elapsed
                if task not in done:
                    task.cancel()
                    break
                # Provide received message to the caller
                yield task.result()

        return _put_in_queue, _generator()


@pytest.fixture(scope='session')
def mqtt_broker():
    '''
    Fixture provisioning MQTT broker in form of Docker container
    '''
    client = docker.DockerClient()

    port = 1883
    # Broker configuration file
    config = [
        f'listener {port}',
        'allow_anonymous true',
        'log_type debug',
        'log_type error',
        'log_type warning',
        'log_type notice',
        'log_type information',
        'log_dest stdout',
        'connection_messages true',
        ''
    ]
    config_str = "\n".join(config)

    tmpdir = tempfile.mkdtemp(dir=os.getenv('RUNNER_TEMP'))
    print(f'Using {tmpdir} as temporary directory')
    mqtt_config_file = os.path.join(tmpdir, 'mosquitto.conf')
    with open(mqtt_config_file, 'w', encoding='ascii') as mqtt_config:
        mqtt_config.write(config_str)

    container = client.containers.run(
        'eclipse-mosquitto', detach=True,
        remove=True,
        ports={f'{port}/tcp': (None, port)},
        volumes={tmpdir: {'bind': '/mosquitto/config'}},
    )
    # Allow the broker to startup and ready for the clients
    time.sleep(1)

    # Pass the execution to the test using the fixture
    yield
    # Clean the container up once the test completes
    container.stop()
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.mark.asyncio
async def test_online_sensor_last_will(
    # `pylint` mistekenly treats fixture as re-definition
    # pylint: disable=redefined-outer-name, unused-argument
    mqtt_broker
):
    '''
    Tests online sensor for properly utilizing MQTT last will to set the state
    if the code doesn't disconnect cleanly
    '''
    async def mqtt_client_destroy(self):
        '''
        Function to shutdown MQTT client sockets instead of doing clean
        disconnect
        '''
        # This triggers call to `_reset_sockets()` in Paho MQTT
        del self._client
        # Re-instantiate fresh Paho MQTT client so Async MQTT won't trip over
        # missing `_client` attribute
        # pylint: disable=protected-access
        self._client = MqttClient(hostname='dummy')._client

    with mock_config():
        with mock_serial():
            # Replace MQTT disconnect with the function to forcibly shutdown
            # MQTT client sockets, simulating unclean disconnect
            with patch.object(MqttClient, 'disconnect', mqtt_client_destroy):
                # Setup MQTT keep-alive to a minimal value, so that unclean
                # disconnect will result in last will message being sent upon
                # keep-alive elapses
                with patch.object(MqttClient, '_keepalive', 1):
                    await async_main()

    # Use MQTT client that allows for receiving MQTT messages over configured
    # time interval, to avoid blocking execution indefinitely (as parent MQTT
    # client does)
    mqtt_client = MqttClientTimedSubscribe(
        # Timeout value should be sufficiently longer that keep-alive interval
        # above, so that last will feature will be activated
        hostname='127.0.0.1', subscribe_timeout=5
    )

    # Attempt to receive online sensor state upon unclean shutdown of the MQTT
    # client
    async with mqtt_client as client:
        async with client.unfiltered_messages() as messages:
            await client.subscribe('homeassistant/binary_sensor/+/+/state', 0)
            online_sensor_state = [
                x.payload.decode() async for x in messages
                if 'IS_ONLINE' in x.topic
            ]
            # Verify only single message received
            assert len(online_sensor_state) == 1
            # Verify the sensor state should be OFF during unclean shutdown
            assert online_sensor_state.pop() == json.dumps({'value': 'OFF'})


def test_online_sensor():
    '''
    Tests for handling pseudo online sensor under timeout condition.
    '''

    mqtt_publish_call_args_for_timeout = []
    with mock_serial(simulate_timeout=True):
        with mock_mqtt() as mqtt_mocks:
            with mock_config():
                main()
                mqtt_publish_call_args_for_timeout = (
                    mqtt_mocks['publish'].call_args_list
                )

    assert call(
        topic='homeassistant/binary_sensor/CE301_00123456'
        '/CE301_00123456_IS_ONLINE/state',
        payload=json.dumps({'value': 'OFF'}),
    ) in mqtt_publish_call_args_for_timeout
