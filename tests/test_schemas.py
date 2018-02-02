# -*- coding: utf-8 -*-

"""Tests for JSON schema libraries."""

import json
import os

import pytest

from f8a_worker.schemas import (SchemaRef, SchemaLibrary,
                                BundledSchemaLibrary,
                                BundledDynamicSchemaLibrary,
                                SchemaLookupError,
                                SchemaModuleAttributeError,
                                SchemaImportError,
                                load_all_worker_schemas,
                                assert_no_two_consecutive_schemas_are_same)


@pytest.mark.offline
class TestSchemaRef(object):

    def test_next_addition(self):
        schema_ref = SchemaRef("example", "1-0-0")
        assert schema_ref.next_addition() == SchemaRef("example", "1-0-1")

    def test_next_revision(self):
        schema_ref = SchemaRef("example", "1-0-0")
        assert schema_ref.next_revision() == SchemaRef("example", "1-1-0")

    def test_next_model(self):
        schema_ref = SchemaRef("example", "1-0-0")
        assert schema_ref.next_model() == SchemaRef("example", "2-0-0")


@pytest.mark.offline
class TestSchemaLibrary(object):

    def test_schema_lookup(self, tmpdir):
        library = SchemaLibrary(str(tmpdir))
        requested_schema = SchemaRef("example", "1-0-0")
        with pytest.raises(SchemaLookupError):
            library.load_schema(requested_schema)
        schema_path = tmpdir.join("example-v1-0-0.schema.json")
        dummy_schema = {"dummy-schema": "example"}
        serialized_schema = json.dumps(dummy_schema).encode('utf-8')
        schema_path.write_binary(serialized_schema)
        assert library.read_binary_schema(requested_schema) == serialized_schema
        assert library.load_schema(requested_schema) == dummy_schema

    def test_bundled_schema_lookup(self, tmpdir):
        pkgdir = tmpdir.mkdir(tmpdir.basename)
        pkgdir.ensure("__init__.py")
        schemadir = pkgdir.mkdir("schemas")
        module = pkgdir.pyimport()
        library = BundledSchemaLibrary("schemas", module.__name__)
        requested_schema = SchemaRef("example", "1-0-0")
        with pytest.raises(SchemaLookupError):
            library.load_schema(requested_schema)
        schema_path = schemadir.join("example-v1-0-0.schema.json")
        dummy_schema = {"dummy-schema": "example"}
        serialized_schema = json.dumps(dummy_schema).encode('utf-8')
        schema_path.write_binary(serialized_schema)
        assert library.read_binary_schema(requested_schema) == serialized_schema
        assert library.load_schema(requested_schema) == dummy_schema

    def test_bundled_dynamic_schema_lookup(self, tmpdir, monkeypatch):
        pkgdir = tmpdir.mkdir(tmpdir.basename)
        pkgdir.ensure("__init__.py")
        schemadir = pkgdir.mkdir("schemas")
        schemadir.ensure("__init__.py")
        library = BundledDynamicSchemaLibrary('.'.join([tmpdir.basename, "schemas"]))
        schema1 = SchemaRef("example", "1-0-0")
        schema2 = SchemaRef("example2", "1-0-0")
        schema3 = SchemaRef("example3", "1-0-0")
        schema4 = SchemaRef("example4", "1-0-0")
        schema5 = SchemaRef("example4", "2-0-0")  # intentionally example4
        schema6 = SchemaRef("example6", "2-0-0")
        with pytest.raises(SchemaImportError):
            library.load_schema_class_and_role(schema1)
        # sch2 doesn't have the ROLE_v1_0_0 variable
        sch2 = "import jsl;\nclass Schema(jsl.Document):\n x = jsl.StringField()\n"
        # sch3 doesn't have THE_SCHEMA variable
        sch3 = sch2 + "\nROLE_v1_0_0 = 'v1-0-0'\n"
        # sch4 is ok
        sch4 = sch3 + "\nTHE_SCHEMA = Schema\n"
        # no sch5; sch6 is ok and has two roles
        sch6 = sch4 + "\nROLE_v2_0_0 = 'v2-0-0'\n"
        schemadir.join("example2.py").write(sch2)
        schemadir.join("example3.py").write(sch3)
        schemadir.join("example4.py").write(sch4)
        schemadir.join("example6.py").write(sch6)
        monkeypatch.syspath_prepend(pkgdir.dirname)
        with pytest.raises(SchemaModuleAttributeError):
            library.load_schema_class_and_role(schema2)
        with pytest.raises(SchemaModuleAttributeError):
            library.load_schema_class_and_role(schema3)
        klass, role = library.load_schema_class_and_role(schema4)
        assert "x" in dir(klass)
        assert role == "v1-0-0"
        with pytest.raises(SchemaModuleAttributeError):
            # example 5 is the same as example 4, but doesn't have the required version 2-0-0
            library.load_schema_class_and_role(schema5)
        klass6, role6 = library.load_schema_class_and_role(schema6)
        assert "x" in dir(klass)
        assert role6 == "v2-0-0"


@pytest.mark.offline
class TestGeneratedSchemas(object):
    schemas_path = os.path.join("data", "schemas")

    def test_dynamic_schemas_against_generated(self):
        """Check for the schema chanes.

        This test checks that previously generated schemas haven't changed
        by later modifications to the Python definitions.
        When you define new schemas or new versions of schemas, you'll need
        to run data/schemas/generate.py to get them generated.
        """
        all_schemas = load_all_worker_schemas()
        test_library = BundledSchemaLibrary(self.schemas_path, __package__)
        for ref, schema in all_schemas.items():
            assert test_library.load_schema(ref) == schema


@pytest.mark.offline
class TestSchemaSequence:
    def test_no_two_consecutive_schemas_are_same(self):
        assert_no_two_consecutive_schemas_are_same(load_all_worker_schemas)
