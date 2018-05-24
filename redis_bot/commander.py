#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import functools
import re
import shlex
import random
import asyncio
import logging

from redis_bot.lib import RedisToChan
from fuzzywuzzy import fuzz


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


def luckierThan(value):
    """True if you where luckier than value (value C ]0,1])"""
    return value <= random.random()


def split_command(body):
    try:
        command_line = shlex.split(body)
    except ValueError:
        logger.warning("Could not shlex.split the body {},"
                       " fallbacking behavior".format(body))
        command_line = re.split(r"\s+", body)
    try:
        command = command_line[0]
    except IndexError:
        command = ""
    args = command_line[1:]
    return command, args, command_line


def default_condition(function, message):
    command, args, command_line = split_command(message.get("body", ""))
    return command == "bot{}".format(function.__name__)


def close_condition(function, message, threshold=90):
    command, args, command_line = split_command(message.get("body", ""))
    return fuzz.ratio(
        command,
        "bot{}".format(function.__name__)) < threshold


conditions_functions = []
public_functions = []


class register():
    def __init__(self, rooms=None, condition=None, hide=False):
        self.hide = hide
        self.condition = condition
        self.rooms = rooms

    def __call__(self, function):
        function.bot_condition = self.condition
        logger.debug("Registering the function {}".format(function))

        @functools.wraps(function)
        def wrapped_function(*args, **kwargs):
            return function(*args, **kwargs)

        def condition(message):
            if self.condition:
                res = self.condition(message)
            else:
                res = default_condition(function, message)
            res = res and (self.rooms is None or message["mucroom"] in self.rooms)
            return res

        conditions_functions.append(
            (condition, wrapped_function)
        )
        if not self.hide:
            public_functions.append(wrapped_function)
        return wrapped_function


def react(condition, rooms=None, hide=True):
    return register(condition=condition, rooms=rooms, hide=hide)


@register()
def help(mess, *args):
    return "\n".join(
        [
            "bot{}: {}".format(
                function.__name__,
                (function.__doc__.splitlines()[0]
                 if function.__doc__ else "not documented")
            )
            for function in public_functions
        ]
    )


def dispatch(mess):
    body = mess.get("body", "")

    command, args, command_line = split_command(body)

    candidates = [
        function for condition, function in conditions_functions
        if condition and condition(mess)
    ]
    if candidates:
        function = candidates[0]
        res = function(mess, *args)
    else:
        # find ones close enough
        close_candidates = [
            function for condition, function in conditions_functions
            if function in public_functions and
            function.bot_condition is None and (
                    (
                        command.startswith("bot")
                        and
                        close_condition(function, mess)
                    )
                    or
                    (
                        not command.startswith("bot")
                        and
                        close_condition(function, mess)
                    )
            )
        ]
        if close_candidates and not mess["from_bot"]:
            if len(close_candidates) == 1:
                res = close_candidates[0](mess, *args)
                res += "\n{}: It was bot{}, NOOOOB!".format(
                    mess["mucnick"],
                    close_candidates[0].__name__
                )
            else:
                candidates_and_scores = [
                    (
                        candidate,
                        fuzz.ratio(candidate.__name__, command)
                    )
                    for candidate in close_candidates
                ]
                bestscore = max(candidates_and_scores,
                               key=lambda c_n_s: c_n_s[1])[1]
                close_candidates = [
                    candidate
                    for candidate, score in candidates_and_scores
                    if score == bestscore
                ]
                if len(close_candidates) == 1:
                    res = close_candidates[0](mess, *args)
                    res += "\n{}: It was bot{}, NOOOOB!".format(
                        mess["mucnick"],
                        close_candidates[0].__name__
                    )
                else:
                    close_candidates_names = ["bot{}".format(f.__name__)
                                              for f in close_candidates]
                    res = (
                        "Did you mean any of " +
                        ", ".join(close_candidates_names) + "?"
                    )
        else:
            res = None
    return res


async def listen():
    logger.info("Start listening")
    rtc = RedisToChan()
    async for mess in rtc.listen():
        body = dispatch(mess)
        if body is not None:
            await rtc.answer(mess, body)


def sync_listen():
    asyncio.get_event_loop().run_until_complete(listen())


botcmd = register()
botreact = react
