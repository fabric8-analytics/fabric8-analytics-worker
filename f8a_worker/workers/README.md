Worker definition in Bayesian
-----------------------------

Worker node is a self-contained unit encapsulating particular type of workload
in the form of application container.
Containers are orchestrated via OpenShift (or Docker Compose) and fine grained
control is established by message passing through a message bus, but these
infrastructure details are outside of the scope of this document.

## Overview
Tasks are currently abstracted via [Celery](https://celeryproject.org), which
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
files](...)) which model time or data dependencies between tasks. You can
easily visualize flows by prepared script in `hack/visualize_flows.sh`. Make
sure you have Selinon installed using `hack/update_selinon.sh` - Selinon has
no releases now as it is still under development, so you have to install
particular commit version.

## BaseTask
For the purpose of better code reuse and maintainability every new worker type
should be implemented as a subclass of BaseTask abstract base class that is
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
* `execute()`: Task's workhorse, called from `run(). Abstract method.
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
a failed state for tasks in Selinon/Celery, as returning False or None could be
a valid result depending on the context. That means that if something really
goes wrong, we’ll know about it, and we’ll have the precise traceback stored
at our disposal. The failed task can be automatically rescheduled after
predefined time period, if it makes sense.

For up2date list of all currently implemented tasks see
[nodes.yml](https://github.com/fabric8-analytics/fabric8-analytics-worker/blob/master/f8a_worker/dispatcher/nodes.yml)
Selinon configuration file that states all flow nodes available in the system.

## Utility workers

Workers that assist other workers but don't provide exposed data.

* [binwalk.py](binwalk.py) - Find and extract interesting files / data from binary images

* [digester.py](digester.py) - Computes various digests of all files found in target cache path

* [init.py](init.py) - This task initializes whole analysis

* [linguist.py](linguist.py) - GitHub's tool to figure out what language is used in code

## Data Workers

Workers that provide data exposed to the user.

* [csmock_worker.py](csmock_worker.py) - Static code analysis.

* [code_metrics.py](code_metrics.py) - Code metrics computation.

* [CVEchecker.py](CVEchecker.py) - Queries CVE database for security issues.

* [githuber.py](githuber.py) - Gets popularity and issues data from Github

* [licenser.py](licenser.py) - Check licences of all files of a package

* [mercator.py](mercator.py) - Extracts ecosystem specific information and transforms it to a common scheme

* [oscryptocatcher.py](oscryptocatcher.py) - Matches crypto algorithms in sources based on content

* [BigQuery_GH](docs/bigquery_gh.md) ([bigquery_gh.py](bigquery_gh.py)) - Gets GitHub package usage information from BigQuery
