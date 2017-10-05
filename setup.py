#!/usr/bin/env python3
from setuptools import setup, find_packages


def get_requirements():
    with open('requirements.txt') as fd:
        return fd.read().splitlines()


setup(
    name='f8a_worker',
    version='0.2',
    scripts=[
        'hack/workers.sh',
        'hack/worker-liveness.sh',
        'hack/worker-readiness.sh'
    ],
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
