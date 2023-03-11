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
Module to hold various constants
"""
from addict import Dict

DEFAULT_CONFIG_FILE = '/etc/energomera/config.yaml'

# Default parameters to use when configuration file has none
DEFAULT_CONFIG = Dict(
    general=dict(
        oneshot=False,
        intercycle_delay=30,
        logging_level='error',
        include_default_parameters=False,
    ),
    meter=dict(
        timeout=30,
    ),
    mqtt=dict(
        tls=True,
    ),
    parameters=[
        dict(address='ET0PE',
             name='Cumulative energy',
             device_class='energy',
             state_class='total_increasing',
             unit='kWh',
             response_idx=0,
             additional_data=None,
             entity_name=None),
        dict(address='ECMPE',
             name='Monthly energy',
             device_class='energy',
             state_class='total',
             unit='kWh',
             response_idx=0,
             additional_data=None,
             entity_name=None),
        dict(address='ENMPE',
             name='Cumulative energy, previous month',
             device_class='energy',
             state_class='total_increasing',
             unit='kWh',
             response_idx=0,
             additional_data='{{ energomera_prev_month }}',
             entity_name='ENMPE_PREV_MONTH'),
        dict(address='EAMPE',
             name='Previous month energy',
             device_class='energy',
             state_class='total',
             unit='kWh',
             response_idx=0,
             additional_data='{{ energomera_prev_month }}',
             entity_name='ECMPE_PREV_MONTH'),
        dict(address='ECDPE',
             name='Daily energy',
             device_class='energy',
             state_class='total',
             unit='kWh',
             response_idx=0,
             additional_data=None,
             entity_name=None),
        dict(address='POWPP',
             name=[
                 'Active energy, phase A',
                 'Active energy, phase B',
                 'Active energy, phase C'
             ],
             device_class='power',
             state_class='measurement',
             unit='kW',
             response_idx=None,
             additional_data=None,
             entity_name=None),
        dict(address='POWEP',
             name='Active energy',
             device_class='power',
             state_class='measurement',
             unit='kW',
             response_idx=None,
             additional_data=None,
             entity_name=None),
        dict(address='VOLTA',
             name=[
                 'Voltage, phase A',
                 'Voltage, phase B',
                 'Voltage, phase C'
             ],
             device_class='voltage',
             state_class='measurement',
             unit='V',
             response_idx=None,
             additional_data=None,
             entity_name=None),
        dict(address='VNULL',
             name='Neutral voltage',
             device_class='voltage',
             state_class='measurement',
             unit='V',
             response_idx=None,
             additional_data=None,
             entity_name=None),
        dict(address='CURRE',
             name=[
                 'Current, phase A',
                 'Current, phase B',
                 'Current, phase C'
             ],
             device_class='current',
             state_class='measurement',
             unit='A',
             response_idx=None,
             additional_data=None,
             entity_name=None),
        dict(address='FREQU',
             name='Frequency',
             device_class='frequency',
             state_class='measurement',
             unit='Hz',
             response_idx=None,
             additional_data=None,
             entity_name=None),
    ]
)
