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

See [workers/README.md](./f8a_worker/workers/README.md) for a listing of the concrete services.

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

## Some tips for running tests locally


**Reusing an existing virtualenv for multiple test runs**

When a virtualenv already is setup you can run tests like so:

```
source /path/to/python_env/bin/activate
NOVENV=1 ./runtest.sh
```

This will not create a virtualenv every time.


**Forcing image builds while testing**

When some changes are made to code that will change the docker image, it is good to rebuild images locally for testing. This can re-build can be forced like so:

```
REBUILD=1 ./runtest.sh 
```
