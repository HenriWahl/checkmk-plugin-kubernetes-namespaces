# checkmk-agent-plugin-kubernetes

## Overview

This project provides a Checkmk agent plugin for monitoring Kubernetes namespaces and their resources.
It includes server-side WATO settings for configuring some monitoring parameters.

An agent plugin will be installed on the Kubernetes nodes. The plugin will collect the data deliver it to the Checkmk server.
The collected data are retrieved from local `kubectl` commands.

## Features

- Monitor Kubernetes namespaces and these resources:
  - CronJobs
  - DaemonSets
  - Deployments
  - PersistentVolumes
  - Pods
  - ReplicaSets
- Set percentage thresholds for PersistentVolume usage
- Set thresholds for CronJob counts
- Special feature: monitors the capacity of persistent volumes

## Development

For local development the included `docker-compose.yml` file might help.

## Usage

Upload the `.mkp` file to your Checkmk instance.

The plugin will be available in the agent bakery.

The resulting services in Checkmk will look like this:

![Checkmk Kubernetes Namespaces Plugin](docs/checkmk-k8s-status.png)

If just some cluster resources should be monitored, the WATO rule can be used to customize some namespaces:

![Checkmk Kubernetes Namespaces Plugin](docs/checkmk-k8s-wato.png)

## License

This project is licensed under the GPL3 license.