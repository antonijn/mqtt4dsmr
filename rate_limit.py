# Copyright (c) 2024, Antonie Blom
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

import logging
import time
from threading import Thread, Condition


class DirectPublisher:
    def __init__(self, schema, client):
        self.schema = schema
        self.client = client

    def publish(self, telegram):
        self.schema.publish(self.client, telegram)


class RateLimitedPublisher:
    def __init__(self, schema, client, interval):
        self.schema = schema
        self.client = client
        self.interval_ns = interval * 1000000000
        self.telegram = None
        self.msg = Condition()
        self.tick = Condition()
        self.started = Condition()
        self.total_msgs = 0
        self.epoch = time.monotonic_ns()
        self.rate_ok = True

        logging.debug(f'Rate limiter epoch: {self.epoch} ns')

        # Make sure we return an object with a consistent state. msg and
        # tick conditions must be in locked or waiting state before
        # we start receiving messages
        with self.started:
            Thread(target=self.ticker, daemon=True).start()
            self.started.wait()
            Thread(target=self.loop, daemon=True).start()
            self.started.wait()

    def next_ts(self):
        return self.epoch + self.interval_ns * self.total_msgs

    def ticker(self):
        with self.tick:
            # Notify parent thread that we're holding the tick lock, and
            # it's okay to continue
            with self.started:
                self.started.notify()

            while True:
                self.tick.wait()
                sleep_ns = self.next_ts() - time.monotonic_ns()
                if sleep_ns > 0:
                    logging.debug(f'Rate limiter delay: {sleep_ns} ns')
                    time.sleep(sleep_ns / 1000000000)
                else:
                    logging.debug('No rate limiter delay')

                with self.msg:
                    self.rate_ok = True
                    self.msg.notify()

    def loop(self):
        with self.msg:
            # Notify parent thread that we're holding the msg lock, and
            # it's okay to continue
            with self.started:
                self.started.notify()

            while True:
                self.msg.wait()
                if not self.rate_ok:
                    logging.debug('Got message, but not ready to publish yet')
                    continue

                if self.telegram is not None:
                    logging.debug('Ready to publish message')
                    self.schema.publish(self.client, self.telegram)
                    self.total_msgs += 1
                    self.telegram = None

                    with self.tick:
                        # Reset; if the rate is still okay after sending
                        # a new message, the ticker will tell us so
                        self.rate_ok = False
                        self.tick.notify()
                else:
                    logging.debug('Ready to publish, but no message queued')

    def publish(self, telegram):
        with self.msg:
            self.telegram = telegram
            self.msg.notify()
