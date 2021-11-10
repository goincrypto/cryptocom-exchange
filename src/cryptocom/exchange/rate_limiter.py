import asyncio
import math
import time
import traceback

from contextlib import asynccontextmanager


class RateLimiter:
    def __init__(self,
                 rate_limit: int,
                 period: float or int,  # takes seconds
                 concurrency_limit: int) -> None:
        if not rate_limit or rate_limit < 1:
            raise ValueError('rate limit must be non zero positive number')
        if not concurrency_limit or concurrency_limit < 1:
            raise ValueError('concurrent limit must be non zero positive number')

        self.rate_limit = rate_limit
        self.period = period
        self.tokens_queue = asyncio.Queue(rate_limit)
        self.tokens_consumer_task = asyncio.create_task(self.consume_tokens())
        self.semaphore = asyncio.Semaphore(concurrency_limit)

    async def add_token(self) -> None:
        await self.tokens_queue.put(1)
        return None

    async def consume_tokens(self):
        try:
            consumption_rate = self.period / self.rate_limit
            last_consumption_time = 0

            while True:
                if self.tokens_queue.empty():
                    await asyncio.sleep(consumption_rate)
                    continue

                current_consumption_time = time.monotonic()
                total_tokens = self.tokens_queue.qsize()
                tokens_to_consume = self.get_tokens_amount_to_consume(
                    consumption_rate,
                    current_consumption_time,
                    last_consumption_time,
                    total_tokens
                )

                for _ in range(0, tokens_to_consume):
                    self.tokens_queue.get_nowait()

                last_consumption_time = time.monotonic()

                await asyncio.sleep(consumption_rate)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            raise

    @staticmethod
    def get_tokens_amount_to_consume(consumption_rate, current_consumption_time,
                                     last_consumption_time, total_tokens):
        time_from_last_consumption = current_consumption_time - last_consumption_time
        calculated_tokens_to_consume = math.floor(time_from_last_consumption / consumption_rate)
        tokens_to_consume = min(total_tokens, calculated_tokens_to_consume)

        return tokens_to_consume

    @asynccontextmanager
    async def throttle(self):
        await self.semaphore.acquire()
        await self.add_token()
        try:
            yield
        finally:
            self.semaphore.release()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            pass
            # print(traceback.format_exc())

        await self.close()

    async def close(self) -> None:
        if self.tokens_consumer_task and not self.tokens_consumer_task.cancelled():
            try:
                self.tokens_consumer_task.cancel()
                await self.tokens_consumer_task
            except asyncio.CancelledError:
                # print(traceback.format_exc())
                pass

            except Exception as e:
                # print(traceback.format_exc())
                raise
