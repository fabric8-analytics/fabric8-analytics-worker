#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import os.path
import json

from cucoslib.workers import LicenseCheckTask
from cucoslib.schemas import get_schema_ref

def license_check_sample(data_dir, target_dir):
    input_path = os.path.join(data_dir, 'license')
    args = {'cache_path': input_path}
    task = LicenseCheckTask()
    results = task.execute(arguments=args)

    # Check task self-validation
    task.validate_result(results)

    # Get schema ref to determine output location
    schema_ref = get_schema_ref(results)
    sample_file = "{0.name}-v{0.version}.json".format(schema_ref)
    output_path = os.path.join(target_dir, sample_file)
    sample_data = json.dumps(results, sort_keys=True, indent=2).encode("utf-8")
    with open(output_path, "wb") as f:
        f.write(sample_data)
    print(output_path)

if __name__ == "__main__":
    this_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.abspath(os.path.join(this_dir, '../tests/data'))
    relative_target = "../../server/tests/offline/schema_samples/"
    target_dir = os.path.abspath(os.path.join(this_dir, relative_target))
    license_check_sample(data_dir, target_dir)
