'''
Tests for handling HomeAssistant configuration payloads.
'''
import json
from unittest.mock import call
import pytest
from energomera_hass_mqtt.main import main

serial_exchange = [
    {
        'receive_bytes': b'/?!\r\n',
        'send_bytes': b'/EKT5CE301v12\r\n',
    },
    {
        'receive_bytes': b'\x06051\r\n',
        'send_bytes': b'\x01P0\x02(777777)\x03\x20',
    },
    {
        'receive_bytes': b'\x01P1\x02(dummy)\x03\x03',
        'send_bytes': b'\x06',
    },
    {
        'receive_bytes': b'\x01R1\x02HELLO()\x03M',
        'send_bytes': b'\x02HELLO(2,CE301,12,00123456,dummy)\r\n\x03\x01',
    },
    {
        'receive_bytes': b'\x01R1\x02ET0PE()\x037',
        'send_bytes':
            b'\x02ET0PE(16907.9477764)\r\n'
            b'ET0PE(11504.3875082)\r\n'
            b'ET0PE(3628.2698795)\r\n'
            b'ET0PE(1775.2903887)\r\n'
            b'ET0PE(0.0)\r\n'
            b'ET0PE(0.0)\r\n\x03\x04',
    },
    {
        'receive_bytes': b'\x01R1\x02ET0PE()\x037',
        'send_bytes':
            b'\x02ET0PE(16907.9477764)\r\n'
            b'ET0PE(11504.3875082)\r\n'
            b'ET0PE(3628.2698795)\r\n'
            b'ET0PE(1775.2903887)\r\n'
            b'ET0PE(0.0)\r\n'
            b'ET0PE(0.0)\r\n\x03\x04',
    },
]

CONFIG_YAML = '''
    general:
        oneshot: true
    meter:
      port: dummy_serial
      password: dummy
      timeout: 1
    mqtt:
      # This is important as Docker-backed tests spawn the broker exposed
      # on the localhost
      host: 127.0.0.1
      user: mqtt_dummy_user
      password: mqtt_dummy_password
    parameters:
        - address: ET0PE
          device_class: energy
          name: Cumulative energy (updated)
          response_idx: 0
          state_class: total_increasing
          unit: kWh
        - address: ET0PE
          device_class: energy
          name: Cumulative energy (updated 1)
          response_idx: 0
          state_class: total_increasing
          unit: kWh
'''


@pytest.mark.usefixtures('mock_config')
@pytest.mark.serial_exchange(serial_exchange)
@pytest.mark.config_yaml(CONFIG_YAML)
def test_config_payload_update(mock_serial, mock_mqtt):
    '''
    Tests for configuration payload to be sent again once it changes (e.g.
    through interpolation).
    '''
    main()
    mock_serial['_send'].assert_has_calls(
        [call(x['receive_bytes']) for x in serial_exchange]
    )

    mock_mqtt['publish'].assert_has_calls([
        call(
            topic='homeassistant/sensor/CE301_00123456'
            '/CE301_00123456_ET0PE/config',
            payload=json.dumps(
                {
                    'name': 'Cumulative energy (updated)',
                    'device': {
                        'name': '00123456',
                        'ids': 'CE301_00123456',
                        'model': 'CE301',
                        'sw_version': '12',
                    },
                    'device_class': 'energy',
                    'unique_id': 'CE301_00123456_ET0PE',
                    'object_id': 'CE301_00123456_ET0PE',
                    'unit_of_measurement': 'kWh',
                    'state_class': 'total_increasing',
                    'state_topic': 'homeassistant/sensor/CE301_00123456'
                                   '/CE301_00123456_ET0PE/state',
                    'value_template': '{{ value_json.value }}',
                }
            ),
            retain=True,
        ),
    ])

    mock_mqtt['publish'].assert_has_calls([
        call(
            topic='homeassistant/sensor/CE301_00123456'
            '/CE301_00123456_ET0PE/config',
            payload=json.dumps(
                {
                    'name': 'Cumulative energy (updated 1)',
                    'device': {
                        'name': '00123456',
                        'ids': 'CE301_00123456',
                        'model': 'CE301',
                        'sw_version': '12',
                    },
                    'device_class': 'energy',
                    'unique_id': 'CE301_00123456_ET0PE',
                    'object_id': 'CE301_00123456_ET0PE',
                    'unit_of_measurement': 'kWh',
                    'state_class': 'total_increasing',
                    'state_topic': 'homeassistant/sensor/CE301_00123456'
                                   '/CE301_00123456_ET0PE/state',
                    'value_template': '{{ value_json.value }}',
                }
            ),
            retain=True,
        ),
    ])
