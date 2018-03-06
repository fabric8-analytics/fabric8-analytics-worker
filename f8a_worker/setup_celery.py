#!/usr/bin/env python

"""Functions to setup Selinon/Celery."""

import os
import logging
from celery import Celery
from celery import __version__ as celery_version
from selinon import Config, selinon_version
from f8a_worker.celery_settings import CelerySettings

YAML_FILES_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'dispatcher')


_logger = logging.getLogger(__name__)


def get_dispatcher_config_files():
    """Get config files (nodes and flows) for dispatcher/selinon."""
    nodes_yml = os.path.join(YAML_FILES_DIR, 'nodes.yml')

    if not os.path.isfile(nodes_yml):
        nodes_yml = os.path.join(YAML_FILES_DIR, 'nodes.yaml')
        if not os.path.isfile(nodes_yml):
            raise ValueError("nodes.yml not found in config")

    flows_dir = os.path.join(YAML_FILES_DIR, 'flows')

    if not os.path.isdir(flows_dir):
        raise ValueError("Missing directory flows in config")

    flows = []
    for flow in os.listdir(flows_dir):
        if flow.startswith("."):
            _logger.debug("Ignoring hidden file '%s' in flows directory", flow)
            continue
        if not flow.endswith(".yml") and not flow.endswith(".yaml"):
            raise ValueError("Unknown file found in config: '%s'" % flow)
        flows.append(os.path.join(flows_dir, flow))

    return nodes_yml, flows


def init_selinon(app=None):
    """Init Selinon configuration.

    :param app: celery application, if omitted Selinon flow handling tasks will not be registered
    """
    if app is not None:
        Config.set_celery_app(app)

    nodes_config, flows_config = get_dispatcher_config_files()
    Config.set_config_yaml(nodes_config, flows_config)


def init_celery(app=None, result_backend=True):
    """Init Celery configuration.

    :param app: celery configuration, if omitted, application will be instantiated
    :param result_backend: True if Celery should connect to result backend
    """
    # Keep this for debugging purposes for now
    _logger.debug(">>> Selinon version is %s" % selinon_version)
    _logger.debug(">>> Celery version is %s" % celery_version)

    if not result_backend:
        CelerySettings.disable_result_backend()

    if app is None:
        app = Celery('tasks')
        app.config_from_object(CelerySettings)
    else:
        app.config_from_object(CelerySettings)
