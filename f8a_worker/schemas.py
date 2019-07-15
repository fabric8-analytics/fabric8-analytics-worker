"""Utilities for accessing and working with JSON schemas."""

import abc
from collections import namedtuple, OrderedDict
from functools import wraps
import importlib
import json
import os.path
import pkgutil

import jsl
import jsonschema


def added_in(role):
    """Provide helper for schema fields added in a particular version.

    Example:
       with added_in(ROLE_v2_0_0) as since_v2_0:
           since_v2_0.new_field_name = ...

    """
    return jsl.Scope(lambda v: v >= role)


def removed_in(role):
    """Provide helper for schema fields removed in a particular version.

    Example:
       with removed_in(ROLE_v2_0_0) as before_v2_0:
           before_v2_0.old_field_name = ...

    """
    return jsl.Scope(lambda v: v < role)


class JSLWithSchemaAttribute(jsl.Document):
    """JSL schema for name, version, url."""

    name = jsl.StringField(required=True, description='Name of the schema',
                           pattern=r'^[a-zA-Z0-9_]+$')
    version = jsl.StringField(required=True, description='Version of the schema',
                              pattern=r'^[0-9]+-[0-9]+-[0-9]+$')
    url = jsl.UriField(required=False, description='Full URL of the schema')


class JSLSchemaBase(jsl.Document):
    """Base class for all schema definitions.

    This class serves as a base class for all schema definitions that should
    include the `schema` object (with `name`, `version` and optional `url`).
    """

    def get_schema(self, role, ordered=True):
        """Override of jsl.Document.get_schema with these changes.

        - an explicit *role* argument is required
        - the *ordered* parameter defaults to True
        """
        schema_as_json = super(JSLSchemaBase, self).get_schema(role, ordered)
        # Set schema title based on the definition ID and active role
        try:
            options = self.Options
            definition_id = options.definition_id
        except AttributeError as exc:
            msg = "Published schema {} missing 'definition_id' option"
            raise TypeError(msg.format(type(self).__name__)) from exc
        title = "{}-{}".format(definition_id, role)
        schema_as_json["title"] = title
        return schema_as_json

    schema = jsl.DocumentField(JSLWithSchemaAttribute,
                               description='Information about schema of this document')


class JSLSchemaBaseWithRelease(JSLSchemaBase):
    """JSL schema for release id."""

    _release = jsl.StringField(
        required=False,
        description='Unique release id in form of "ecosystem:package:version"'
    )


class SchemaRef(namedtuple("SchemaRef", "name version")):
    """Name and version number for a JSON schema."""

    __slots__ = ()  # 3.4.3 compatibility: prevent __dict__ override

    def __str__(self):
        """Represent schema as string."""
        return "{} v{}".format(self.name, self.version)

    # Define new schema versions based on this one
    def _split_version_info(self):
        """Split version info into tuple."""
        return tuple(map(int, self.version.split("-")))

    def _replace_version_info(self, model, revision, addition):
        """Replace version info."""
        version = "-".join(map(str, (model, revision, addition)))
        return self._replace(version=version)

    def next_addition(self):
        """Bump addition."""
        model, revision, addition = self._split_version_info()
        return self._replace_version_info(model, revision, addition + 1)

    def next_revision(self):
        """Bump revision."""
        model, revision, addition = self._split_version_info()
        return self._replace_version_info(model, revision + 1, addition)

    def next_model(self):
        """Bump model."""
        model, revision, addition = self._split_version_info()
        return self._replace_version_info(model + 1, revision, addition)


class SchemaLookupError(LookupError):
    """Failed to find requested schema in schema library."""

    def __init__(self, schema_ref):
        """Initialize object."""
        self.schema_ref = schema_ref

    def __str__(self):
        """Represent as a string."""
        return "Unknown schema: {}".format(self.schema_ref)


class SchemaModuleAttributeError(AttributeError):
    """No such attribute defined."""

    def __init__(self, mod, attribute):
        """Initialize object."""
        self.mod = mod
        self.attribute = attribute

    def __str__(self):
        """Represent as a string."""
        return "Module {} doesn't define attribute {} necessary for automatic schema load".\
            format(self.mod, self.attribute)


class SchemaImportError(ImportError):
    """Failed to import schema from module."""

    def __init__(self, mod):
        """Initialize object."""
        self.mod = mod

    def __str__(self):
        """Represent as a string."""
        return "Can't import schema from module {}".format(self.mod)


class AbstractSchemaLibrary(object, metaclass=abc.ABCMeta):
    """Abstract class for schema."""

    def load_schema(self, schema_ref):
        """Load and parse specified schema from the library."""
        try:
            schema_data = self.read_binary_schema(schema_ref)
        except Exception as exc:
            raise SchemaLookupError(schema_ref) from exc
        return json.loads(schema_data.decode("utf-8"), object_pairs_hook=OrderedDict)

    @abc.abstractmethod
    def read_binary_schema(self, schema_ref):
        """Read raw binary schema from path constructed from given schema ref."""
        raise NotImplementedError('read_binary_schema is abstract method')


class SchemaLibrary(AbstractSchemaLibrary):
    """Load named and versioned JSON schemas."""

    def __init__(self, schema_dir):
        """Initialize object."""
        # Py2 compatibility: use explicit super()
        super(SchemaLibrary, self).__init__()
        self.schema_dir = schema_dir
        self._schema_pattern = os.path.join(schema_dir, "{}-v{}.schema.json")

    def read_binary_schema(self, schema_ref):
        """Read raw binary schema from path constructed from given schema ref."""
        schema_path = self._schema_pattern.format(*schema_ref)
        with open(schema_path, "rb") as schema_file:
            return schema_file.read()


class BundledSchemaLibrary(SchemaLibrary):
    """Load named and version JSON schemas bundled with a Python package."""

    def __init__(self, schema_dir, base_module):
        """Initialize object."""
        # Py2 compatibility: use explicit super()
        super(BundledSchemaLibrary, self).__init__(schema_dir)
        self.base_module = base_module

    def read_binary_schema(self, schema_ref):
        """Read raw binary schema from path constructed from given schema ref."""
        schema_path = self._schema_pattern.format(*schema_ref)
        return pkgutil.get_data(self.base_module, schema_path)


class BundledDynamicSchemaLibrary(AbstractSchemaLibrary):
    """Load named and version JSON schemas bundled with a Python package."""

    def __init__(self, schema_mod_fqn):
        """Initialize object."""
        # Py2 compatibility: use explicit super()
        super(BundledDynamicSchemaLibrary, self).__init__()
        self.schema_mod_fqn = schema_mod_fqn

    def read_binary_schema(self, schema_ref):
        """Read raw binary schema from path constructed from given schema ref."""
        result_class, role = self.load_schema_class_and_role(schema_ref)
        return json.dumps(result_class().get_schema(ordered=True, role=role)).encode('utf-8')

    def load_schema_class_and_role(self, schema_ref):
        """Load schema class and role."""
        module_fqn = '.'.join([self.schema_mod_fqn, schema_ref.name.replace('-', '_')])
        try:
            mod = importlib.import_module(module_fqn)
        except ImportError as e:
            raise SchemaImportError(module_fqn) from e
        role_name = 'ROLE_v{}'.format(schema_ref.version).replace('-', '_')
        result_class_name = 'THE_SCHEMA'
        if not hasattr(mod, role_name):
            raise SchemaModuleAttributeError(mod, role_name)
        if not hasattr(mod, result_class_name):
            raise SchemaModuleAttributeError(mod, result_class_name)
        return getattr(mod, result_class_name), getattr(mod, role_name)

    def _load_all_schema_refs(self):
        """Return all schema references from modules in `self.schema_mod_fqn`.

        The result is an iterable of SchemaRef instances covering all known
        schema modules and references.
        """
        top_pkg = importlib.import_module(self.schema_mod_fqn)
        schemas_to_versions = {}
        for importer, modname, ispkg in pkgutil.iter_modules(top_pkg.__path__):
            if not ispkg:
                mod = importlib.import_module('.'.join([self.schema_mod_fqn, modname]))
                schemas_to_versions[modname] = []
                role_in_development = getattr(mod, "_ROLE_IN_DEVELOPMENT", None)
                for attr in dir(mod):
                    if attr.startswith('ROLE_v'):
                        # Omit version if it's still under active development
                        if getattr(mod, attr) is role_in_development:
                            continue
                        version = attr[len('ROLE_v'):].replace('_', '-')
                        schemas_to_versions[modname].append(version)
        for modname, versions in schemas_to_versions.items():
            for version in versions:
                yield SchemaRef(modname, version)

    def load_all_jsl_definitions(self):
        """Return all JSL definitions from modules in `self.schema_mod_fqn`.

        The result is a dictionary that maps SchemaRef instances to JSL
        document definition and role pairs.
        """
        all_refs = self._load_all_schema_refs()
        return {ref: self.load_schema_class_and_role(ref) for ref in all_refs}

    def load_all_schemas(self):
        """Return all schemas from modules in `self.schema_mod_fqn`.

        The result is a dictionary that maps SchemaRef instances to JSON
        schema dictionaries.
        """
        all_refs = self._load_all_schema_refs()
        return {ref: self.load_schema(ref) for ref in all_refs}


_worker_schemas = BundledDynamicSchemaLibrary("f8a_worker.workers.schemas")
# _external_schemas are schemas that we use to validate responses of services
# that workers communicate with
_external_schemas = BundledSchemaLibrary("schemas", __name__)
load_worker_schema = _worker_schemas.load_schema
load_all_worker_schemas = _worker_schemas.load_all_schemas
load_all_worker_jsl_definitions = _worker_schemas.load_all_jsl_definitions
load_worker_schema_class_and_role = _worker_schemas.load_schema_class_and_role


class SchemaValidator(object):
    """Encapsulation for the provided schema library.

    SchemaValidator encapsulates the provided schema library
    and provides pre/post-condition checking decorators

    >>> schema = SchemaValidator(someSchemaLibrary)

    Pre-condition - input check
    ---------------------------
    The first dictionary parameter of the function is validated against
    the provided schema

    Example:
        >>> @schema.input(SchemaRef("some-schema", "v1"))
        >>> def somefunc(data):
        >>>    pass


    Post-condition - result check
    -----------------------------
    The return value of the function is validated against the provided schema

    Example:
        >>> @schema.result(SchemaRef("some-result-schema", "v1"))
        >>> def somefunc(data):
        >>>    return {'foo': 'bar'}

    """

    def __init__(self, library):
        """Initialize object."""
        self._schema_cache = {}
        self._library = library

    def _ensure_schema(self, name):
        """Load schema if not in cache."""
        if name not in self._schema_cache:
            self._schema_cache[name] = self._library.load_schema(name)

        return self._schema_cache[name]

    def input(self, *args):
        """Define input decorator."""
        def decorator(func):
            """Inner function decorator."""
            @wraps(func)
            def wrapper(*largs, **kwargs):
                s = self._ensure_schema(args[0])
                arg = None
                # find first dict argument, hack so that the same decorator
                # works for functions as well as for methods
                for a in largs:
                    if isinstance(a, dict):
                        arg = a
                        break
                jsonschema.validate(arg, s)
                return func(*largs, **kwargs)
            return wrapper
        return decorator

    def result(self, *args):
        """Define result decorator."""
        def decorator(func):
            """Inner function decorator."""
            @wraps(func)
            def wrapper(*largs, **kwargs):
                s = self._ensure_schema(args[0])
                r = func(*largs, **kwargs)
                jsonschema.validate(r, s)
                return r
            return wrapper
        return decorator


external_schema = SchemaValidator(_external_schemas)


def get_schema_ref(analysis, default=None):
    """Retrieve a schema reference from a component analysis."""
    try:
        schema_ref_dict = analysis["schema"]
    except KeyError as exc:
        if default is None:
            raise SchemaLookupError("No schema reference found") from exc
        return default
    try:
        result = SchemaRef(**schema_ref_dict)
        if any(field is None for field in result):
            raise TypeError
    except TypeError as exc:
        msg = "Malformed schema reference: {!r}"
        raise SchemaLookupError(msg.format(schema_ref_dict)) from exc
    return result


def pop_schema_ref(analysis, default=None):
    """Retrieve and remove a schema reference from a component analysis."""
    schema_ref = get_schema_ref(analysis, default)
    analysis.pop("schema", None)
    return schema_ref


def set_schema_ref(analysis, schema_ref):
    """Set the schema reference for a component analysis."""
    analysis["schema"] = schema_ref._asdict()


def schema_version_comparator_key(schema_version):
    """Split the schema version on return it as a tuple of numbers.

    Function that you can use for `sorted`'s `key` argument when sorting schema versions.
    """
    parts = schema_version.split('-')
    parts = [int(p) for p in parts]
    return parts


def assert_no_two_consecutive_schemas_are_same(load_all_schemas):
    """Check that no two consecutive versions of schema are the same.

    Test utility function used by both server and worker test suites. It makes sure
    that no two consecutive versions of schema are the same (if they are, we don't need
    one of them)

    :arg load_all_schemas: load_all_schemas method of a BundledDynamicSchemaLibrary instance
    """
    all_schemas = load_all_schemas()
    schema_to_versions = {}
    for ref, schema in load_all_schemas().items():
        schema_to_versions.setdefault(ref.name, [])
        schema_to_versions[ref.name].append(ref.version)
    for name, versions in schema_to_versions.items():
        versions.sort(key=schema_version_comparator_key)

    for name, versions in schema_to_versions.items():
        for i in range(0, len(versions) - 1):
            v1, v2 = versions[i], versions[i + 1]
            assert all_schemas[SchemaRef(name, v1)] != all_schemas[SchemaRef(name, v2)], \
                '{} schema versions {} and {} are the same'.format(name, v1, v2)
