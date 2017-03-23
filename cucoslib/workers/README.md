Worker definition in CuCoS-lib
-------------------------------

Worker node is a self-contained unit encapsulating particular type of workload
in the form of application container.
Containers are orchestrated via Kubernetes and fine grained control is
established by message passing through a message bus, but these infrastructure
details are outside of the scope of this document.

## Overview
Tasks are currently abstracted via Celery, which is a distributed task queue
implemented on top of many different message passing mechanisms (AMQP, ZeroMQ,
Redis, ORM mapping ...) and different storage backends for (non-complimentary)
message persistence. Celery makes spawning a new task as simple as
asynchronously invoking a particular function/method:


```
@app.task
def add_task(x, y):
    return x + y

```

## BaseTask
For the purpose of better code reuse and maintainability every new worker type
should be implemented as a subclass of BaseTask abstract base class:


```
class BaseTask(celery.Task):
    def __init__(self):
    def call(self):
    def run(self):
    def execute(self):
    def on_after_execute(self):
    def child_tasks():
    def callback_task():
    …
```

What is the actual purpose of this base class and its methods ?

* call(): The way how to 'start' a task is to make an instance of the task, call its call() method and pass it a dict with task arguments
* run(): Celery transparently calls run(), which calls execute() and on_after_execute().
* execute(): Task's workhorse, called from run(). Abstract method. Once implemented returns dictionary with results.
* on_after_execute(): Called in run() after execute(). Writes result into DB below prefix key.
* child_tasks(): Tasks to be spawned after finishing the task.
* callback_task(): Task to execute as a chord header after all child tasks are done executing.

Process flow:
```
START TASK -> Task.execute() -> Task.on_after_execute() -> run children tasks -> TASK END
```

The execute() method is followed by post-hook on_after_execute method().
This post-hook writes the obtained data to database.
Any unhandled exception raised in execute() will toggle the task into a failed state.
The on_after_execute() may be overridden by concrete subclasses, but that should not be
needed in most cases.

## Example worker task
Now, let’s implement an example worker that computes digests of all
the files found in the cache path, what code do we need to write?

```
class DigesterTask(BaseTask):
    name = 'cucoslib.workers.digester'
    description = 'Computes digests of files'

    def execute(self, arguments):
        results = {}
        results = compute_digests(arguments)
        return results
```

As can be seen from the above example, task implementers don’t need to bother
with all the gory details of messaging and queueing - simply implement an
execute() method where you compose a dictionary and return it.
Nice and shiny, but what if something goes wrong ?
The good thing is that raising an exception is a canonical mechanism to signal
a failed state for tasks in Celery, as returning False or None could be a valid
result depending on the context. That means that if something really goes wrong,
we’ll know about it, and we’ll have the precise traceback stored at our disposal.
The failed task can be automatically rescheduled after predefined time period,
if it makes sense, because if the task failed with a traceback, what are the
odds that rescheduling it will suddenly make it work?

### Using a worker task

First you need to have a message bus and metadata database:
```
$ cd cucos
$ docker-compose start broker postgres
```

Then execute the celery worker:
```
$ celery worker -A cucoslib.workers -Q DigesterTask_v1 -l debug
```

Then use it, for example:
```
import json
from cucoslib.ecosystem import Ecosystem
from cucoslib.models import Analysis, WorkerResult
from cucoslib.workers import DigesterTask

task = DigesterTask()
analysis = Analysis()
task.database.add(analysis)
task.database.commit()
args = {'ecosystem': Ecosystem.get_ecosystem_by_name('npm').id,
        'name': 'serve-static',
        'version': '1.7.1',
        'document_id': analysis.id,
        'cache_path: '/tmp')
task.call(args).wait()
result = task.database.query(WorkerResult).\
            filter(WorkerResult.analysis_id == analysis.id,
                   WorkerResult.worker == task.metadata_name()).\
            first()
data = result.task_result
print(json.dumps(data, indent=2))
```

If you want to execute the worker without all the broker/database/task queue
machinery, it can also be executed from command line:

```
$ hack/cucos-execute-worker LicenseCheckTask /usr/lib/python3.4/site-packages/setuptools
```

This is equivalent to running worker execute() method.

## Utility workers

Workers that assit other workers but don't provide exposed data.

* [binwalk.py](binwalk.py) - Find and extract interesting files / data from binary images

* [digester.py](digester.py) - Computes various digests of all files found in target cache path

* [init.py](init.py) - This task initializes whole analysis

* [linguist.py](linguist.py) - GitHub's tool to figure out what language is used in code

## Data Workers

Workers that provide data exposed to the user.

* [csmock_worker.py](csmock_worker.py) - Static code analysis.

* [CVEchecker.py](CVEchecker.py) - Queries CVE database for security issues.

* [githuber.py](githuber.py) - Gets popularity and issues data from Github

* [licenser.py](licenser.py) - Check licences of all files of a package

* [mercator.py](mercator.py) - Extracts ecosystem specific information and transforms it to a common scheme

* [oscryptocatcher.py](oscryptocatcher.py) - Matches crypto algorithms in sources based on content

* [BigQuery_GH](docs/bigquery_gh.md) ([bigquery_gh.py](bigquery_gh.py)) - Gets GitHub package usage information from BigQuery
