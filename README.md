Fabric8-Analytics Core library and services
-------------------------------------------

This library provides basic infrastructure for development of services and concrete implemementation of services. 

The following libraries are provided:

* Database abstraction
* Task Queue Worker/Node abstraction
* Utilities
  * File tree walker with filtering
  * One-to-many dictionary
  * Shell command wrapper with timeout support

See ./f8a_worker/workers/README.md for a listing of the concrete services.  

## Contributing

See our [contributing guidelines](https://github.com/fabric8-analytics/common/blob/master/CONTRIBUTING.md) for more info.

## Running worker environment with docker-compose

There are two sets of workers - API and ingestion. API workers serve requests that are passed from API endpoint. Ingestion workers are used for background data ingestion. To run them use:
```shell
$ docker-compose up worker-api worker-ingestion
```

# Running the tests locally

## Docker based API testing

Run the tests in a container using the helper
script:
```shell
$ ./runtests.sh
```

(The above command assumes you have passwordless docker invocation configured -
if you don't, then `sudo` will be necessary to enable docker invocation).

If you're changing dependencies rather than just editing source code locally,
you will need images to be rebuilt when invoking `runtest.sh`. You
can set environment variable `REBUILD=1` to request image rebuilding.

If the offline virtualenv based tests have been run, then this may complain
about mismatched locations in compiled files. Those can be deleted using:
```shell
$ find -name *.pyc -delete
```

NOTE: Running the container based tests is likely to cause any already
running local Fabric8-Analytics instance launched via Docker Compose to fall over due to
changes in the SELinux labels on mounted volumes, and may also cause
spurious test failures.


## Virtualenv based offline testing

Test cases marked with `pytest.mark.offline` may be executed without having a
Docker daemon running locally.

To configure a virtualenv (called `f8a-worker` in the example) to run these
tests:
```shell
(f8a-worker) $ python -m pip install -r requirements.txt
(f8a-worker) $ python -m pip install -r tests/requirements.txt
```

The marked offline tests can then be run as:
```shell
(f8a-worker) $ py.test -m offline tests/
```

If the Docker container based tests have been run, then this may complain
about mismatched locations in compiled files. Those can be deleted using:
```shell
(f8a-worker) $ sudo find -name *.pyc -delete
```

# Testing against not-yet-released worker dependencies

The `Dockerfile.tests` file is set up to install any
`f8a-license-check-unreleased.rpm` file stored locally in this directory.
In combination with the `license-check-worker/make_rpm.sh` script in the
data-mining-tools repo, this feature can be used to run the worker tests
against a version of `f8a-license-check` that is not yet released.
