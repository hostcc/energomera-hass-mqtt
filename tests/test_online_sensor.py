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
import socket
import shutil
import tempfile
import asyncio
import time
import json
from unittest.mock import patch, call
import docker
import pytest
from energomera_hass_mqtt.mqtt_client import MqttClient
from energomera_hass_mqtt.main import async_main, main


@pytest.fixture
def mqtt_broker(request, unused_tcp_port):  # pylint: disable=too-many-locals
    '''
    Fixture provisioning MQTT broker in form of Docker container.

    Users/password could be provided with test mark:

    ```
    @pytest.mark.mqtt_broker_users(
        'mqtt_user1:mqtt_password1',
        'mqtt_user2:mqtt_password2',
        ...
    )
    ```
    '''
    client = docker.DockerClient.from_env()

    port = unused_tcp_port
    container_path = '/mosquitto/config'
    password_file = 'mosquitto.users'

    # Attempt to get MQTT users from test mark
    users = getattr(
        request.node.get_closest_marker("mqtt_broker_users"),
        'args', []
    )

    # Broker configuration file
    config = [
        f'listener {port}',
        f'allow_anonymous {"false" if users else "true"}',
        'log_type debug',
        'log_type error',
        'log_type warning',
        'log_type notice',
        'log_type information',
        'log_dest stdout',
        'connection_messages true',
    ]

    tmpdir = tempfile.mkdtemp(
        dir=os.getenv('RUNNER_TEMP') or os.getenv('TOX_WORK_DIR')
    )
    print(f'Using {tmpdir} as temporary directory for MQTT broker configs')

    if users:
        # Store provided users and password to plaintext file
        config.append(f'password_file {container_path}/{password_file}')
        mqtt_password_file = os.path.join(tmpdir, password_file)
        with open(mqtt_password_file, 'w', encoding='ascii') as mqtt_password:
            # The content should have last line ending with LF
            mqtt_password.write("\n".join(users) + "\n")

    mqtt_config_file = os.path.join(tmpdir, 'mosquitto.conf')
    with open(mqtt_config_file, 'w', encoding='ascii') as mqtt_config:
        # The content should have last line ending with LF
        mqtt_config.write("\n".join(config) + "\n")

    container = client.containers.run(
        'eclipse-mosquitto', detach=True,
        remove=True,
        ports={f'{port}/tcp': (None, port)},
        volumes={tmpdir: {'bind': container_path}},
    )

    if users:
        # Issue command to convert the password file from cleartext to hashed
        # version compatible with MQTT broker, and then signal it to re-read
        # the configuration
        cmd = (
            f'sh -c "mosquitto_passwd -U {container_path}/{password_file}'
            ' && killall -SIGHUP mosquitto"'
        )
        exit_code, output = container.exec_run(cmd)
        if exit_code != 0:
            raise Exception(output)

    # Ensure the broker is ready by connecting to its port from host and
    # immediately closing the connection
    reachable = False
    last_exception = None
    for _ in range(30):
        try:
            socket.create_connection(
                ('127.0.0.1', port), timeout=3
            ).close()
            reachable = True
            break
        except Exception as exc:
            last_exception = exc  # noqa: F841
            time.sleep(1)

    if not reachable:
        raise Exception(
            f'Container for MQTT broker is not reachable over port {port}'
            ' ({last_exception})'
        )

    print(
        f'MQTT broker container is ready on port {port} (ID: {container.id})'
    )

    # Pass the execution to the test using the fixture
    yield dict(port=port)

    print(f"\nDestroying MQTT broker container (ID {container.id})")
    # Clean the container up once the test completes
    container.stop()
    try:
        container.wait()
    # Ignore exceptio if the container has gone already
    except docker.errors.NotFound:
        pass
    shutil.rmtree(tmpdir, ignore_errors=True)


async def read_online_sensor_states(port, code=None, timeout=5):
    '''
    Retrieves online sensor states from MQTT broker during alotted time frame -
    traditional MQTT client subscribe() awaits for the messages indefinitely
    '''
    online_sensor_states = []

    async def listen(sensor_states):
        '''
        Attempts to receive online sensor states
        '''
        async with MqttClient(
            hostname='127.0.0.1', port=port
        ) as client:
            async with client.messages() as messages:
                await client.subscribe(
                    'homeassistant/binary_sensor/+/+/state', 0
                )
                async for msg in messages:
                    if 'IS_ONLINE' in msg.topic.value:
                        sensor_states.append(msg.payload.decode())

    task = asyncio.create_task(listen(online_sensor_states))
    # Execute optional code (e.g. normal program run) before awaiting for
    # sensor states
    if code:
        await code()

    # Wait for configured time to allow sensor states to be retrieved
    try:
        await asyncio.wait_for(
            task, timeout=timeout
        )
    # pylint:disable=broad-except
    except Exception:
        pass

    return online_sensor_states


@pytest.mark.usefixtures('mock_config', 'mock_serial')
@pytest.mark.asyncio
async def test_online_sensor_last_will(
    # `pylint` mistekenly treats fixture as re-definition
    # pylint: disable=redefined-outer-name, unused-argument
    mqtt_broker,
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
        self._client = MqttClient(
            hostname='dummy', port=mqtt_broker['port']
        )._client

    # Replace MQTT disconnect with the function to forcibly shutdown
    # MQTT client sockets, simulating unclean disconnect
    with patch.object(MqttClient, 'disconnect', mqtt_client_destroy):
        # Setup MQTT keep-alive to a minimal value, so that unclean
        # disconnect will result in last will message being sent upon
        # keep-alive elapses
        with patch.object(MqttClient, '_keepalive', 1):
            await async_main(mqtt_port=mqtt_broker['port'])

    online_sensor_states = await read_online_sensor_states(
        port=mqtt_broker['port']
    )
    # Verify the last sensor state should be OFF during unclean shutdown
    assert len(online_sensor_states) == 1
    assert online_sensor_states.pop() == json.dumps({'value': 'OFF'})


@pytest.mark.usefixtures('mock_config', 'mock_serial')
@pytest.mark.asyncio
async def test_online_sensor_normal_run(
    # `pylint` mistekenly treats fixture as re-definition
    # pylint: disable=redefined-outer-name, unused-argument
    mqtt_broker,
):
    '''
    Tests online sensor for properly reflecting online sensors state during
    normal run
    '''

    # Attempt to receive online sensor state upon normal program run
    async def normal_run():
        await async_main(mqtt_port=mqtt_broker['port'])

    online_sensor_states = await read_online_sensor_states(
        code=normal_run, port=mqtt_broker['port']
    )
    # There should be two messages for online sensor - first with 'ON'
    # value during the program run, and another with 'OFF' value
    # generated at program exit
    assert len(online_sensor_states) == 2
    assert online_sensor_states == [
        json.dumps({'value': 'ON'}),
        json.dumps({'value': 'OFF'})
    ]


@pytest.mark.usefixtures('mock_config', 'mock_serial')
@pytest.mark.serial_simulate_timeout(True)
def test_online_sensor(mock_mqtt):
    '''
    Tests for handling pseudo online sensor under timeout condition.
    '''

    main()

    # Verify the last call to MQTT contains online sensor being OFF
    assert call(
        topic='homeassistant/binary_sensor/CE301_00123456'
        '/CE301_00123456_IS_ONLINE/state',
        payload=json.dumps({'value': 'OFF'}),
    ) == mock_mqtt['publish'].call_args_list[-1]
