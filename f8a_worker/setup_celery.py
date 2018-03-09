#!/usr/bin/env python

"""Functions to setup Selinon/Celery."""

from celery import Celery
from celery import __version__ as celery_version
import logging
from pathlib import Path
from selinon import Config, selinon_version
from f8a_worker.celery_settings import CelerySettings

YAML_FILES_DIR = Path(__file__).resolve().parent / 'dispatcher'

_logger = logging.getLogger(__name__)


def get_dispatcher_config_files():
    """Get config files (nodes and flows) for dispatcher/selinon."""
    nodes_yml = YAML_FILES_DIR / 'nodes.yml'

    if not nodes_yml.is_file():
        nodes_yml = YAML_FILES_DIR / 'nodes.yaml'
        if not nodes_yml.is_file():
            raise ValueError("nodes.yml not found in config")

    flows_dir = YAML_FILES_DIR / 'flows'

    if not flows_dir.is_dir():
        raise ValueError("Missing directory flows in config")

    flows = []
    for flow in flows_dir.iterdir():
        if flow.name.startswith("."):
            _logger.debug("Ignoring hidden file '%s' in flows directory", flow)
            continue
        if not flow.name.endswith((".yml", ".yaml")):
            raise ValueError("Unknown file found in config: '%s'" % flow)
        flows.append(str(flow))

    return str(nodes_yml), flows


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
