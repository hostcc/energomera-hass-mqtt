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

Python package to read data from `Energomera energy meter
<https://energomera-by.translate.goog/products/?_x_tr_sl=ru&_x_tr_tl=en&_x_tr_hl=en-US&_x_tr_pto=wapp&_x_tr_sch=http>`_
(possibly supporting `others similar
<http://www.energomera.ru/en/products/meters>`_) and send over to HomeAssistant
using MQTT.

The package has been developed with CE301BY three-phase meter.

Dependencies
============

* Pending PR to ``iec62056_21`` for transport improvements:
  https://github.com/pwitab/iec62056-21/pull/29

Quick start
===========

Since there are direct dependencies no package is published on PyPI and you'll
need to install it directly from Github:

.. code:: shell

     pip install git+https://github.com/hostcc/energomera-hass-mqtt@master

Usage
=====

.. code::

   usage: energomera-hass-mqtt [-h] [-c CONFIG_FILE] [-a] [-d] [-o]

   options:
   -h, --help            show this help message and exit
   -c CONFIG_FILE, --config-file CONFIG_FILE
                           Path to configuration file (default: '/etc/energomera/config.yaml')
   -a, --dry-run         Dry run, do not actually send any data
   -d, --debug           Enable debug logging
   -o, --one-shot        Run only once, then exit

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
            #  cycles. Is also used as MQTT keepalive interval upon which the
            #  broker will consider the client disconnected if no response
            intercycle_delay:
            # (string) default ``error``: logging level, one of ``critical``,
            #  ``error``, ``warning``, ``info`` or ``debug``
            logging_level:
            # (bool) default ``false``: if enabled makes parameters a
            # combination of default ones plus those defined in the
            # configuration file, no check for duplicates is performed!
            include_default_parameters:
        # Energy meter parameters
        meter:
            # (string) Serial port (e.g. /dev/ttyUSB0)
            port:
            # (string) Password to meter for administrative session, manufacturer's
            #  default is '777777'
            password:
            # (number) default ``30``: Timeout for meter communications
            timeout:
        # MQTT parameters
        mqtt:
            # (string) Hostname or IP address of MQTT broker
            host:
            # (number) default ``1883``: Port of MQTT broker
            port:
            # (string) optional: MQTT user name
            user:
            # (string) optional: MQTT user password
            password:
            # (string) default ``homeassistant``: Preffix to MQTT topic names,
            #  should correspond to one set in HomeAssistant for auto-discovery
            hass_discovery_prefix:
            # (bool) default ``true``: Whether to enable TLS with MQTT broker
            tls:
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
              # (string) - optional: Category of the HASS sensor entity
              entity_category:


Interpolation expressions
-------------------------

``parameters`` section supports following expressions:

        - ``{{ energomera_prev_month }}``: Previous month in meter's format,
          defaults to one month back
        - ``{{ energomera_prev_day }}``: Previous day in meter's format,
          default to one day back

All expressions support passing optional argument as ``(...)`` to specify how far
interpolated result should go in the past. Whitespaces around the brackets,
both inner and outer, are ignored. Specifying empty argument results in
using a default value as per interpolation specification above.

For example, ``{{ energomera_prev_day (5) }}`` will result in meter-specific
timestamp returned for the date being 5 days ago. An use case for that might be
intermittent connectivity to the meter where the readings aren't sent to
collecting system on cadence thus have gaps in data points.

Environment variables
=====================

Following environment variables might be provided overriding corresponding
configuration file entries:

* ``MQTT_HOST``: Host or IP address of MQTT broker
* ``MQTT_PORT``: Same but for the port
* ``MQTT_USER``: User name to connect to MQTT broker with
* ``MQTT_PASSWORD``: Same but for the password

``systemd`` support
===================

Sample service definition for ``systemd`` is provided under
`systemd/ <https://github.com/hostcc/energomera-hass-mqtt/tree/master/systemd>`_
directory.

Docker support
==============

There are Docker images available if you would like to run it as Docker container - you could use
``ghcr.io/hostcc/energomera-hass-mqtt:latest`` or
``ghcr.io/hostcc/energomera-hass-mqtt:<release version>``.

As of writing, the images are built to ARM v6/v7 and ARM64 platforms.

.. note::

   For ARMv6 you might need to specify image variant explicitly, in case the
   container engine detects it incorrectly and resulting image doesn't run as
   expected. To do that just add ``--variant v6`` to ``pull`` command


To run the program as container you will need to create a directory on the host
and put ``config.yaml`` relevant to your setup there.

Then, assuming the directory is called ``config`` and resides relative to
current directory, and the serial port the meter is connected to is
``/dev/ttyUSB0`` the following command will run it

.. code::

  $ docker run --device /dev/ttyUSB0 -v `pwd`/config:/etc/energomera/ \
    ghcr.io/hostcc/energomera-hass-mqtt:latest


Documentation
=============

Please see `online documentation <https://energomera-hass-mqtt.readthedocs.io>`_ for
details on the API package provides.
