.. image::  https://github.com/hostcc/energomera-hass-mqtt/actions/workflows/main.yml/badge.svg?branch=master
   :target: https://github.com/hostcc/energomera-hass-mqtt/tree/master
   :alt: Github workflow status
.. image:: https://readthedocs.org/projects/energomera-hass-mqtt/badge/?version=stable
   :target: https://energomera-hass-mqtt.readthedocs.io/en/stable
   :alt: ReadTheDocs status
.. image:: https://img.shields.io/github/v/release/hostcc/energomera-hass-mqtt
   :target: https://github.com/hostcc/energomera-hass-mqtt/releases/latest
   :alt: Latest GitHub release
.. image:: https://img.shields.io/pypi/v/energomera-hass-mqtt
   :target: https://pypi.org/project/energomera-hass-mqtt/
   :alt: Latest PyPI version

Description
===========

Python package to read data from Energomera energy meter and send over to
HomeAssistant using MQTT.

Dependencies
============

* Pending PR to ``iec62056_21`` for transport improvements:
  https://github.com/pwitab/iec62056-21/pull/29

Quick start
===========

Since there are direct dependencies no package is published on PyPI and you'll
need to install it directly from Github:

.. code:: shell

     pip install git+https://github.com/hostcc/energomera-hass-mqtt@main

Usage
=====

.. code::

   usage: energomera-hass-mqtt [-h] [-c CONFIG_FILE]

   optional arguments:
    -h, --help            show this help message and exit
    -c CONFIG_FILE, --config-file CONFIG_FILE
       Path to configuration file (default: '/etc/energomera/config.yaml')

Configuration file format
=========================

Configuration file is in YAML format and supports following elements:

.. code:: yaml

        # (optional) General parameters
        general:
            # (bool) default ``false``: perform single processing cycle and
            #  exit
            oneshot:
            # (number) default ``30``: delay in seconds between processing
            #  cycles
            intercycle_delay:
            # (string) default ``error``: logging level, one of ``critical``,
            #  ``error``, ``warning``, ``info`` or ``debug``
            logging_level:

        # Energy meter parameters
        meter:
            # (string) Serial port (e.g. /dev/ttyUSB0)
            port:
            # (string) Password to meter for administrative session, manufacturer's
            #  default is '777777'
            password:
        # MQTT parameters
        mqtt:
            # (string) Hostname or IP address of MQTT broker
            host:
            # (string) optional: MQTT user name
            user:
            # (string) optional: MQTT user password
            password:
            # (string) default ``homeassistant``: Preffix to MQTT topic names,
            #  should correspond to one set in HomeAssistant for auto-discovery
            hass_discovery_prefix:
        # (list of mappings) - optional: Energy meter parameters to process and
        #  properties of corresponding HASS sensor
        parameters:
            - # (string) IEC address (e.g. ``POWEP``)
              address:
              # (string or list) HASS Sensor name for the entry. If IEC address
              #  provides multi-value reponse, this could be a list with the
              #  number of entries equals to number of values in response
              name:
              # (string) Device class of the HASS sensor
              device_class:
              # (string) State class of the HASS sensor
              state_class:
              # (string) Unit of measurement for the HASS sensor
              unit:
              # (string) - optional: Additional data to read the parameter with
              #  (argument to parameter's address)
              additional_data:
              # (string) - optional: Entity name for the HASS sensor, will be
              #  used to generate its unique ID. If omitted the ``address`` is
              #  used instead. Use of this option might be needed if your
              #  configuration contains several entries of meter's parameters
              #  of same address, but with different ``additional_data``
              entity_name:
              # (number) - optional: Zero-based index to pick an entry from
              #  multi-value response to meter's parameter
              response_idx:


``parameters`` section supports following expressions:

        - ``{{ energomera_prev_month }}``: Previous month in meter's format
        - ``{{ energomera_prev_day }}``: Previous day in meter's format


``systemd`` support
===================

Sample service definition for ``systemd`` is provided under
`<https://github.com/hostcc/energomera-hass-mqtt/tree/main/systemd>`_
directory.
