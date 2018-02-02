#!/usr/bin/env python3

"""Project setup file for the fabric8 analytics worker project."""

import os
from setuptools import setup, find_packages


def get_requirements():
    """Parse all packages mentioned in the 'requirements.txt' file."""
    with open('requirements.txt') as fd:
        return fd.read().splitlines()


setup(
    name='f8a_worker',
    version='0.2',
    scripts=[
        'hack/queue_conf.py',
        'hack/workers.sh',
        'hack/worker-queues-env.sh',
        'hack/worker-pre-hook.sh',
        'hack/worker-liveness.sh',
        'hack/worker-readiness.sh'
    ],
    package_data={
        'f8a_worker': [
            os.path.join('dispatcher', 'migration_dir', '*.json')
        ]
    },
    packages=find_packages(exclude=['tests', 'tests.*']),
    include_package_data=True,
    install_requires=get_requirements(),
    author='Pavel Odvody',
    author_email='podvody@redhat.com',
    description='fabric8-analytics workers & utilities',
    license='GPLv3',
    keywords='fabric8-analytics analysis worker',
    url='https://github.com/fabric8-analytics/fabric8-analytics-worker'
)
