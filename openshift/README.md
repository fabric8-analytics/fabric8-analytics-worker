# Deploying Bayesian workers

First make sure you're logged in to the right cluster and on the right project:

```
$ oc project
```

Note this guide assumes that secrets and config maps have already been deployed.

To deploy the workers, simply run:

```
./deploy.sh
```

The command above will deploy both ingestion and API workers.

