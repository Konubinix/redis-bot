#!/usr/bin/env python
# -*- coding:utf-8 -*-

from setuptools import setup, find_packages

setup(
    name='redis-bot',
    description='Tools to help create a bot',
    author='Samuel Loury',
    author_email='konubinixweb@gmail.com',
    license='MIT',
    packages=find_packages(),
    package_data={'': ['*.j2']},
    install_requires=[
        "asyncio_redis",
        "fuzzywuzzy",
    ],
)
