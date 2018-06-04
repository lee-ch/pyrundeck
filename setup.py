'''
PyRundeck Rundeck API Python Wrapper
'''
import os
import re
import sys
from setuptools import setup, find_packages
from rundeck import VERSION


project = 'pyrundeck'
requires = [
    'requests>=1.2.0',
]

README = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'README.rst')
try:
    with open(README, 'r') as fh:
        long_description = fh.read()
except IOError:
    long_description = 'Rundeck API Python client'

setup(
    name=project,
    license='None',
    version=VERSION,
    packages=find_packages(exclude=['tests', 'tests.*']),
    description='Rundeck API Python client',
    long_description=long_description,
    url='https://github.com/lee-ch/{}'.format(project),
    author='',
    author_email='',
    maintainer='',
    maintainer_email='',
    install_requires=requires,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Topic :: System :: Software Distribution',
        'Topic :: System :: Systems Administration',
        'Topic :: Utilities',
    ],
)