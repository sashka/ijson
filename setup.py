# -*- coding:utf-8 -*-
from setuptools import setup

setup(
    name = 'ijson',
    version = '0.8.0',
    author = 'Ivan Sagalaev',
    author_email = 'Maniac@SoftwareManiacs.Org',
    packages = ['ijson'],
    url = 'https://launchpad.net/ijson',
    license = 'LICENSE.txt',
    description = 'A Python wrapper to YAJL providing standard iterator interface to streaming JSON parsing',
    long_description = open('README.rst').read(),
    test_suite='tests',
)
