[![Build Status](https://ci.centos.org/view/Devtools/job/devtools-fabric8-analytics-worker-f8a-build-master/badge/icon)](https://ci.centos.org/view/Devtools/job/devtools-fabric8-analytics-worker-f8a-build-master/)

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

#### Coding standards

- You can use scripts `run-linter.sh` and `check-docstyle.sh` to check if the code follows [PEP 8](https://www.python.org/dev/peps/pep-0008/) and [PEP 257](https://www.python.org/dev/peps/pep-0257/) coding standards. These scripts can be run w/o any arguments:

```
./run-linter.sh
./check-docstyle.sh
```

The first script checks the indentation, line lengths, variable names, white space around operators etc. The second
script checks all documentation strings - its presence and format. Please fix any warnings and errors reported by these
scripts.

#### Code complexity measurement

The scripts `measure-cyclomatic-complexity.sh` and `measure-maintainability-index.sh` are used to measure code complexity. These scripts can be run w/o any arguments:

```
./measure-cyclomatic-complexity.sh
./measure-maintainability-index.sh
```

The first script measures cyclomatic complexity of all Python sources found in the repository. Please see [this table](https://radon.readthedocs.io/en/latest/commandline.html#the-cc-command) for further explanation how to comprehend the results.

The second script measures maintainability index of all Python sources found in the repository. Please see [the following link](https://radon.readthedocs.io/en/latest/commandline.html#the-mi-command) with explanation of this measurement.

#### Check for scripts written in BASH

The script named `check-bashscripts.sh` can be used to check all BASH scripts (in fact: all files with the `.sh` extension) for various possible issues, incompatibilies, and caveats. This script can be run w/o any arguments:

```
./check-bashscripts.sh
```

Please see [the following link](https://github.com/koalaman/shellcheck) for further explanation, how the ShellCheck works and which issues can be detected.

