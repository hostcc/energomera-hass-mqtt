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
CLI interface to `EnergomeraHassMqtt` class
"""
import sys
import argparse
import logging
import asyncio
from . import EnergomeraHassMqtt, EnergomeraConfig


def process_cmdline(argv):
    """
    Processes command line parameters.

    :param list argv: Command line parameters
    :return: Processed parameters
    :rtype: argparse.Namespace
    """

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-c', '--config-file',
        default='config.yaml',
        help="Path to configuration file (default: '%(default)s')"
    )
    return parser.parse_args(argv)


async def async_main(argv):
    """
    Primary async entry point.

    :param list argv: Command line parameters
    """
    args = process_cmdline(argv)

    config = EnergomeraConfig(args.config_file)
    logging.basicConfig(level=config.logging_level)
    client = EnergomeraHassMqtt(config)
    while True:
        config.interpolate()
        try:
            await client.iec_read_admin()
        except Exception as exc:  # pylint: disable=broad-except
            print('Got exception while processing, skipping to next cycle.'
                  f' Details: {repr(exc)}')
        if config.of.general.oneshot:
            break
        await asyncio.sleep(config.of.general.intercycle_delay)


def main(argv=sys.argv[1:]):
    """
    Main entry point for the CLI.

    :param list argv: Command line parameters, typically `sys.argv`
    """
    try:
        asyncio.run(async_main(argv))
    except AttributeError:
        # Python 3.6 has no `asyncio.run()`, emulate it
        asyncio.get_event_loop().run_until_complete(async_main(argv))


if __name__ == '__main__':
    main()
