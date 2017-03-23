import jsl

from cucoslib.schemas import JSLSchemaBaseWithRelease

# Describe v1-0-0
ROLE_v1_0_0 = "v1-0-0"
ROLE_TITLE = jsl.roles.Var({
    ROLE_v1_0_0: "Blackduck Data v1-0-0"
})


class BlackDuckResult(JSLSchemaBaseWithRelease):
    class Options(object):
        definition_id = "blackduck_data"
        description = "Result of BlackDuck worker"
        additional_properties = True


THE_SCHEMA = BlackDuckResult
