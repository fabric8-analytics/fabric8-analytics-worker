// User-defined function(s) (UDF) for BigQuery.


/** Extract dependencies from NPM shrinkwrap files */
function extractDependencies(row, emit) {
    try {
        var json = JSON.parse(row.content);
    } catch (e) {
        // invalid JSON, nothing to do
        return
    }

    var results = [];
    if (json.hasOwnProperty('dependencies')) {
        results = results.concat(extract(json['dependencies']));
    }

    for (var i = 0; i < results.length; i++) {
        emit(results[i]);
    }
}

function extract(json) {
    var results = [];

    for (var key in json) {
        var name = key;
        var version;
        var details = json[key];
        if (details.hasOwnProperty('version')) {
            version = details['version']
        }
        if (name && version) {
            results.push({name: name, version: version});
            if (details.hasOwnProperty('dependencies')) {
                results.concat(extract(details['dependencies']))
            }
        }
    }
    return results
}

bigquery.defineFunction(
    'extractDependencies',  // Name used to call the function from SQL

    ['content'],  // Input column names

    // JSON representation of the output schema
    [{name: 'name', type: 'string'}, {name: 'version', type: 'string'}],

    // UDF reference
    extractDependencies
);
