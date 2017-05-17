import json
from lxml import etree

_registered_manifest_descriptors = []


def register_manifest_descriptor(descriptor):
    """Registers new ManifestDescriptor.

    All manifest descriptors need to be registered in order to be recognized by Bayesian.
    """
    # TODO: check that we are not adding the same descriptor twice, etc.
    _registered_manifest_descriptors.append(descriptor)


def get_manifest_descriptor_by_filename(filename):
    """Returns ManifestDescriptor for given filename.

    Or None if there is no registered ManifestDescriptor for the given filename.
    """
    return next((x for x in _registered_manifest_descriptors if x.filename == filename), None)


class ManifestDescriptor(object):
    def __init__(self, filename, ecosystem, has_resolved_deps=False, has_recursive_deps=False, validator=lambda x: False):
        """
        :param filename: a typical filename
        :param ecosystem: ecosystem to which this manifest belongs to
        :param has_resolved_deps: indication whether manifest contains exact versions of dependencies
        :param has_recursive_deps: indication whether dependencies in this manifest file are recursive or not
        :param validator: function that can be used to validate this manifest file
        """
        self.filename = filename
        self.ecosystem = ecosystem  # TODO: ecosystem backend!!!
        self.has_resolved_deps = has_resolved_deps
        self.has_recursive_deps = has_recursive_deps
        self.validator = validator

    def validate(self, data):
        return self.validator(data)


def json_validator(data):
    """Very simple JSON validator."""
    try:
        json.loads(data)
    except:
        return False
    return True


def xml_validator(data):
    """Very simple XML validator."""
    try:
        # LXML likes bytes
        etree.fromstring(data.encode())
    except:
        return False
    return True


register_manifest_descriptor(ManifestDescriptor('package.json', 'npm', has_resolved_deps=False, has_recursive_deps=False, validator=json_validator))
register_manifest_descriptor(ManifestDescriptor('npm-shrinkwrap.json', 'npm', has_resolved_deps=True, has_recursive_deps=True, validator=json_validator))
register_manifest_descriptor(ManifestDescriptor('pom.xml', 'maven', has_resolved_deps=True, has_recursive_deps=False, validator=xml_validator))
