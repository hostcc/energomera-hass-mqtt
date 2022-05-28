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
import asyncio
from . import EnergomeraHassMqtt, EnergomeraConfig


async def async_main():
    """
    Primary async entry point.
    """
    tls_context = ssl.SSLContext()
    client = EnergomeraHassMqtt(
        config=EnergomeraConfig('config.yaml'),
    )
    while True:
        try:
            await client.iec_read_admin()
        except Exception as exc:  # pylint: disable=broad-except
            print('Got exception while processing, skipping to next cycle.'
                  f' Details: {repr(exc)}')
        await asyncio.sleep(30)


def main():
    """
    Main entry point for the CLI.
    """
    try:
        asyncio.run(async_main())
    except AttributeError:
        # Python 3.6 has no `asyncio.run()`, emulate it
        asyncio.get_event_loop().run_until_complete(async_main())


if __name__ == '__main__':
    main()
