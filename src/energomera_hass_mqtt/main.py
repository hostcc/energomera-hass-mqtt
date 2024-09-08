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
CLI interface to :class:`EnergomeraHassMqtt` class
"""
from __future__ import annotations
from typing import Optional, TYPE_CHECKING, Tuple
import argparse
import logging
import asyncio
from .config import EnergomeraConfig
from .exceptions import EnergomeraConfigError
from .hass_mqtt import EnergomeraHassMqtt
from .const import DEFAULT_CONFIG_FILE
if TYPE_CHECKING:
    from argparse import Namespace

_LOGGER = logging.getLogger(__name__)


def process_cmdline() -> Tuple[str, Namespace]:
    """
    Processes command line parameters.

    :return: Processed parameters
    """

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-c', '--config-file',
        default=DEFAULT_CONFIG_FILE,
        help="Path to configuration file (default: '%(default)s')"
    )
    return (parser.prog, parser.parse_args())


async def async_main(mqtt_port: Optional[int] = None) -> None:
    """
    Primary async entry point.

    :param mqtt_port: Port of MQTT broker overriding one from config, only
     used by tests since MQTT broker there has random port.
    """
    prog, args = process_cmdline()

    try:
        config = EnergomeraConfig(args.config_file)
    except EnergomeraConfigError as exc:
        logging.error(exc)
        return

    # Override port of MQTT broker (if provided)
    if mqtt_port:
        config.of.mqtt.port = mqtt_port
    logging.basicConfig(level=config.logging_level)

    # Print configuration details
    print(f'Starting {prog}, configuration:')
    print(config)

    client = EnergomeraHassMqtt(config)
    while True:
        config.interpolate()
        try:
            await client.iec_read_admin()
        # Propagate assertion exceptions, mostly from tests
        except AssertionError as exc:
            raise exc
        except Exception as exc:  # pylint: disable=broad-except
            logging.error('Got exception while processing,'
                          ' skipping to next cycle: %s', exc, exc_info=True)
        if config.of.general.oneshot:
            break
        await asyncio.sleep(config.of.general.intercycle_delay)
    await client.finalize()


def main() -> None:
    """
    Main entry point for the CLI.
    """
    asyncio.run(async_main())


if __name__ == '__main__':
    main()
