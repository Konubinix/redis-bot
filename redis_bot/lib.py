#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import json
import base64
import asyncio
import asyncio_redis


def mess_decode(mess):
    mess = {
        key: base64.b64decode(value).decode("utf-8")
        for key, value in json.loads(mess).items()
    }
    return mess


def mess_encode(mess):
    return json.dumps({
        key: base64.b64encode(str(mess[key]).encode("utf-8")).decode("utf-8")
        for key in mess.keys()
    })


class RedisConnection():
    def __init__(
            self,
            host="localhost",
            port=6379,
            channel_from="bot:comm:from",
            channel_to="bot:comm:to",
            channel_control="bot:comm:control",
    ):
        self.host = host
        self.port = port
        self.channel_control = channel_control
        self.channel_to = channel_to
        self.channel_from = channel_from
        self._incoming_connection = None
        self._outgoing_connection = None

    async def _redis_connection(self):
        return await asyncio_redis.Connection.create(
            host=self.host,
            port=self.port
        )

    @property
    async def incoming_connection(self):
        if self._incoming_connection is None:
            self._incoming_connection = await self._redis_connection()
        return self._incoming_connection

    @property
    async def outgoing_connection(self):
        if self._outgoing_connection is None:
            self._outgoing_connection = await self._redis_connection()
        return self._outgoing_connection


class ChanToRedis(RedisConnection):
    async def send(self, mess):
        await (await self.outgoing_connection).publish(
            self.channel_from, mess)

    async def listen(self):
        subscriber = await (await self.incoming_connection).start_subscribe()
        await subscriber.subscribe([
            self.channel_control, self.channel_to
        ])
        while True:
            reply = await subscriber.next_published()
            if reply.channel == self.channel_to:
                mess = mess_decode(reply.value)
                yield mess
            elif reply.channel == self.channel_control:
                mess = mess_decode(reply.value)
                body = mess["body"]
                if body == "ipython":
                    import IPython
                    dict_ = globals()
                    dict_.update(locals())
                    IPython.start_ipython(argv=[], user_ns=dict_)
                elif body == "debug":
                    import ipdb
                    ipdb.set_trace()


class RedisToChan(RedisConnection):
    async def send(self, mess):
        mess = mess_encode(mess)
        await (await self.outgoing_connection).publish(
            self.channel_to, mess)

    async def answer(self, mess, content):
        mess["text"] = content
        await self.send(mess)

    def sync_listen(self):
        loop = asyncio.get_event_loop()
        async_gen = self.listen()
        while True:
            yield loop.run_until_complete(async_gen.__anext__())

    async def listen(self):
        subscriber = await (await self.incoming_connection).start_subscribe()
        await subscriber.subscribe([
            self.channel_from
        ])
        while True:
            reply = await subscriber.next_published()
            mess = mess_decode(reply.value)
            yield mess


rtc = RedisToChan()


def listen_messages():
    yield from rtc.sync_listen()


def answer(mess, body):
    asyncio.get_event_loop().run_until_complete(
        rtc.answer(mess, body)
    )
