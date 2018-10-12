This directory contains versioned schemas for the output of subparts of the analyses
endpoint like the license scanner, written in JSL format.

JSON Schema: http://json-schema.org/documentation.html
JSL: https://jsl.readthedocs.io/en/latest/tutorial.html

The numbering of the schemas uses Snowplow's SchemaVer concept [1], which says
that, given a version number MODEL-REVISION-ADDITION, increment the:

* MODEL when you make a breaking schema change which will prevent validation
  of any historical data (e.g. a new mandatory field has been added)
* REVISION when you make a schema change which may prevent validation of
  some historical data (e.g. only new optional fields have been added, but they
  may conflict with fields in some historical data)
* ADDITION when you make a schema change that is compatible with all
  historical data (i.e. only new optional fields have been added, and they
  cannot conflict with fields in any historical data)

The mechanism in `f8a_worker.schemas` module imposes some rules on how the schema
files should be formed:
- Assuming you define class attribute `schema_ref` in a worker, it must look
  as follows (setting the schema version appropriately for the current worker
  output): `schema_ref = SchemaRef(_analysis_name, '1-0-0')`
- The Python module with jsl schema definition must be placed in this directory
  and must be named `foo.py`, assuming `_analysis_name` from above is `foo`.
- The Python module must contain top level variables:
  - `THE_SCHEMA` - reference to the class that defines schema of worker result
  - `ROLE_v{version}`, e.g. `ROLE_v1_0_0` - variable representing the schema
     version, where dashes in version name are replaced by underscores
- The jsl document that describes the top-level JSON document (usually the one
  that you reference as `THE_SCHEMA`) has to subclass
  `f8a_worker.schemas.JSLSchemaBaseWithRelease` and must not override its `schema`
  or `_release` class attribute.

When adding a new schema or a new version of an existing schema, you'll need
to run `lib/tests/data/schemas/generate.py`. This script will generate new
schemas as necessary, you just need to add them to source control. This is
done in order to ensure old schemas don't change by new additions/changes.
Note that this script can't be run under Python 2, since Python 2 JSON
serialization adds trailing whitespaces to some line endings.

When a new version of a schema is under development, you can set (for example)
`_ROLE_IN_DEVELOPMENT = ROLE_v1_0_0` at the module level to indicate the schema
is still undergoing changes and hence should be omitted from
`load_all_schemas()`. The test suite will then also automatically skip testing
it for consistency (since it hasn't actually been released yet).

All worker schemas are published by API server under
`/api/v1/schemas/component_analyses/<schema>/<version>` path.

TODO: Making the analyses self-describing

[1] http://snowplowanalytics.com/blog/2014/05/13/introducing-schemaver-for-semantic-versioning-of-schemas/
