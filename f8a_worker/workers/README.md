Worker definition in fabric8-analytics
-----------------------------

Worker node is a self-contained unit encapsulating particular type of workload
in the form of application container.
Containers are orchestrated via OpenShift (or Docker Compose) and fine grained
control is established by message passing through a message bus, but these
infrastructure details are outside of the scope of this document.

## Overview
Tasks are currently abstracted via [Celery](http://www.celeryproject.org), which
is a distributed task queue implemented on top of many different message
passing mechanisms (AMQP, ZeroMQ, Redis, ORM mapping ...) and different
storage backends for (non-complimentary) message persistence. Celery makes
spawning a new task as simple as asynchronously invoking a particular
function/method:

```python
@app.task
def add_task(x, y):
    return x + y
```

For the project purposes, there was developed project
[Selinon](https://github.com/selinon) that is written on top of Celery and
provides fine grained control of task flows. Configuration of the whole workflow
is done in simple YAML configuration files (see [dispatcher configuration
files](../dispatcher/)) which model time or data dependencies between tasks. You can
easily visualize flows by prepared script in `hack/visualize_flows.sh`. Make
sure you have Selinon installed.

## BaseTask
For the purpose of better code reuse and maintainability every new worker type
should be implemented as a subclass of `BaseTask` abstract base class that is
derived from `SelinonTask`:

```python
class BaseTask(SelinonTask):
    def run(self):
    def execute(self):
    ...
```

What is the actual purpose of this base class and its methods?

* `run()`: Selinon transparently calls `run()`, which takes care of task audit
  and some additional checks and calls execute()
* `execute()`: Task's workhorse, called from `run()`. Abstract method.
  Once implemented returns dictionary with results.

## Example worker task
Now, let’s implement an example worker that computes digests of all
the files, what code do we need to write?

```python
class DigesterTask(BaseTask):
    def execute(self, arguments):
        results = compute_digests(arguments)
        return results
```

As can be seen from the above example, task implementers don’t need to bother
with all the gory details of messaging and queueing - simply implement an
`execute()` method where you compose a dictionary and return it.
Nice and shiny, but what if something goes wrong ?

The good thing is that raising an exception is a canonical mechanism to signal
a failed state for tasks in Selinon/Celery, as returning `False` or `None` could be
a valid result depending on the context. That means that if something really
goes wrong, we’ll know about it, and we’ll have the precise traceback stored
at our disposal. The failed task can be automatically rescheduled after
predefined time period, if it makes sense.

For up2date list of all currently implemented tasks see
[nodes.yml](../dispatcher/nodes.yml)
Selinon configuration file that states all flow nodes available in the system.

## Utility workers

Workers that assist other workers.

* [InitAnalysisFlow](init_analysis_flow.py) and [InitPackageFlow](init_package_flow.py)- Initializes whole analysis

* [FinalizeTask](finalize.py) and [PackageFinalizeTask](finalize.py) - Finish a flow and store audit

## Data Workers

Workers that expose data to the user.
The following list contains only examples,
because some workers are not part of [any flow](../dispatcher/flows/),
[their code is there](./) just from historical reasons.

* [CVEcheckerTask](CVEchecker.py) - Queries CVE databases for security issues

* [DependencySnapshotTask](dependency_snapshot.py) - Analyzes dependencies

* [DigesterTask](digester.py) - Computes various digests of all files found in target cache path

* [GithubTask](githuber.py) - Gets various info via Github API

* [LibrariesIoTask](libraries_io.py) - Collects statistics from Libraries.io

* [LicenseCheckTask](license.py) - Check licences of all files of a package

* [MercatorTask](mercator.py) - Extracts ecosystem specific information and transforms it to a common scheme
