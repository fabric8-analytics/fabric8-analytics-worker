Bayesian Core library and services
----------------------------------

This library provides basic infrastructure for development of services and concrete implemementation of services. 

The following libraries are provided:

* Database abstraction
* Task Queue Worker/Node abstraction
* Utilities
  * File tree walker with filtering
  * One-to-many dictionary
  * Shell command wrapper with timeout support

See ./cucoslib/workers/README.md for a listing of the concrete services.  

## Running worker environment with docker-compose

```
$ docker-compose up worker
```

# Running the tests locally

## Docker based API testing

Run the tests in a container using the helper
script:

    $ ./runtests.sh

(The above command assumes you have passwordless docker invocation configured -
if you don't, then `sudo` will be necessary to enable docker invocation).

If you're changing dependencies rather than just editing source code locally,
you will need images to be rebuilt when invoking `runtest.sh`. You
can set environment variable `REBUILD=1` to request image rebuilding.

If the offline virtualenv based tests have been run, then this may complain
about mismatched locations in compiled files. Those can be deleted using:

    $ find -name *.pyc -delete

NOTE: Running the container based tests is likely to cause any already
running local Bayesian instance launched via Docker Compose to fall over due to
changes in the SELinux labels on mounted volumes, and may also cause
spurious test failures.


## Virtualenv based offline testing

Test cases marked with `pytest.mark.offline` may be executed without having a
Docker daemon running locally.

To configure a virtualenv (called `cucos-worker` in the example) to run these
tests:

    (cucos-worker) $ python -m pip install -r requirements.txt
    (cucos-worker) $ python -m pip install -r tests/requirements.txt

The marked offline tests can then be run as:

    (cucos-worker) $ py.test -m offline tests/

If the Docker container based tests have been run, then this may complain
about mismatched locations in compiled files. Those can be deleted using:

    (cucos-worker) $ sudo find -name *.pyc -delete


# Testing against not-yet-released worker dependencies

The `Dockerfile.tests` file is set up to install any
`cucos-license-check-unreleased.rpm` file stored locally in this directory.
In combination with the `license-check-worker/make_rpm.sh` script in the
data-mining-tools repo, this feature can be used to run the worker tests
against a version of `cucos-license-check` that is not yet released.
