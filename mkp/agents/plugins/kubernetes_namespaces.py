#!/usr/bin/env python3
# Agent plugin to check the status of Kubernetes namespaces
# Runs on monitored Kubernetes node in /usr/lib/check_mk_agent/plugins/kubernetes_namespaces
# ©2024 henri.wahl@ukdd.de

from json import loads
from os import access, X_OK, environ
from pathlib import Path
from subprocess import run, PIPE
from sys import argv

# Dictionary to store namespaces
namespaces = dict()

# Constant for beginning of time if there is no value for lastScheduleTime or lastSuccessfulTime
TIME_ZERO = '1970-01-01T00:00:00Z'

# Configuration file for the plugin
if environ.get('MK_CONFDIR'):
    CONFIG_FILE=f"{environ.get('MK_CONFDIR')}/{Path(argv[0]).name}.cfg"
else:
    CONFIG_FILE=f'/etc/check_mk/{Path(argv[0]).name}.cfg'


class Namespace:
    """
    Collect all namespace related information
    """
    name = ''
    pods = dict()
    persistent_volumes = dict()
    deployments = dict()
    daemonsets = dict()
    replicasets = dict()
    cronjobs = dict()

    def __init__(self, name):
        """
        Initialize Namespace with a name
        :param name: Name of the namespace
        """
        self.name = name

    def as_dict(self):
        """
        Convert Namespace object to dictionary for final output
        :return: Dictionary
        """
        return {
            'name': self.name,
            'pods': self.pods,
            'persistent_volumes': self.persistent_volumes,
            'deployments': self.deployments,
            'daemonsets': self.daemonsets,
            'replicasets': self.replicasets,
            'cronjobs': self.cronjobs
        }


def configure_plugin():
    """
    Configure the plugin by reading environment variables from a configuration file.

    This function reads the configuration file specified by CONFIG_FILE. Each line in the file
    should be in the format 'KEY=VALUE'. The function sets these key-value pairs as environment
    variables.
    """
    # Check if the configuration file exists and is a file
    try:
        if Path(CONFIG_FILE).exists() and Path(CONFIG_FILE).is_file():
            # Read the configuration file line by line
            for line in Path(CONFIG_FILE).read_text().splitlines():
                # Split each line into key and value
                split_line = line.split('=')
                if len(split_line) == 2:
                    key, value = split_line
                    # Set the environment variable
                    environ[key] = value
    except PermissionError:
        # file does not exist or is not readable
        pass


def get_kubectl_binary() -> str:
    """
    Get the path to the kubectl binary
    :return: Path to kubectl binary
    """
    for path in ['/usr/local/bin/kubectl',
                 '/usr/bin/kubectl',
                 '/bin/kubectl',
                 '/snap/bin/kubectl']:
        # when the path is a file and executable the path is returned
        if Path(path).is_file() and \
                access(path, X_OK):
            return path
    return None


def kubectl(command: str,
            namespace: str = '',
            execute: str = '',
            output_json: bool = True) -> dict:
    """
    Run kubectl command and return the output as a dictionary
    :param command: kubectl command to run
    :param namespace: Kubernetes namespace
    :param execute: Additional command to execute
    :param output_json: Whether to output in JSON format
    :return: Command output as dictionary
    """

    # Construct the base kubectl command
    # Fun fact: variabe KUBECTL is known here because it is defined in the same scope
    #           as this function is called in the main block
    command_line = f'{KUBECTL} {command}'

    # Append the output format to JSON if specified
    if output_json:
        command_line += ' --output json'

    # Append the namespace if specified
    if namespace:
        command_line += f' --namespace {namespace}'

    # Append any additional command to execute if specified
    if execute:
        command_line += f' -- {execute}'

    # Execute the constructed command
    result = run(command_line, shell=True, stdout=PIPE, stderr=PIPE, text=True)

    # Process the command output
    if result.stdout:
        if output_json:
            # Parse and return the JSON output
            return loads(result.stdout)
        else:
            # Return the raw output
            return result.stdout
    else:
        # Return an empty dictionary if there is no output
        return dict()


def get_namespaces() -> list:
    """
    Get the list of namespaces
    :return: List of namespaces
    """
    # Get the list of namespaces using kubectl
    namespaces = kubectl('get namespace')

    # Check if the namespaces dictionary is not empty and contains 'items'
    if namespaces and namespaces.get('items'):
        # Extract and return the list of namespace names
        return [x['metadata']['name'] for x in namespaces['items']]
    else:
        # Return an empty dictionary if no namespaces are found
        return {}


def get_namespace_resources(namespace: str) -> dict:
    """
    Get all resources in a namespace
    :param namespace: Namespace to get resources from
    :return: Dictionary of namespace resources
    """
    # Get all resources in the specified namespace using kubectl
    namespace_resources = kubectl('get all', namespace)

    # Return the dictionary of namespace resources
    return namespace_resources


def get_persistent_volumes(namespace_resources: dict) -> dict:
    """
    Get persistent volumes in a namespace
    :param namespace_resources: Resources in the namespace
    :return: Dictionary of persistent volumes
    """
    # Filter running pods from the namespace resources
    pods = [x for x in namespace_resources['items'] if x.get('kind') == 'Pod'
            and x.get('status', {}).get('phase') == 'Running']
    persistent_volumes = dict()
    # To avoid scanning the same mounted volume multiple times, store its name in this list
    mounts_scanned = list()
    # We run through all pods...
    for pod in pods:
        # ...and check if the pod has volumes to scan...
        if 'volumes' in pod['spec']:
            # ...for every volume in the pod...
            for volume in pod['spec']['volumes']:
                # ...every container has to be inspected...
                for container in pod['spec']['containers']:
                    # ...if persistent volume is used...
                    if 'persistentVolumeClaim' in volume:
                        # ...and the volume is mounted in the container...
                        for mount in container['volumeMounts']:
                            # ...and the mount is not already scanned...
                            if mount['name'] == volume['name'] and \
                                    mount['name'] not in mounts_scanned:
                                # ...execute 'df' command inside the pod to get volume usage
                                df = kubectl(command=f"exec {pod['metadata']['name']}",
                                             namespace=pod['metadata']['namespace'],
                                             execute=f"df {mount['mountPath']}",
                                             output_json=False)
                                # When there is any result form `df` command...
                                if df:
                                    df_lines = df.splitlines()
                                    # ...we run through all lines...
                                    for df_line in df_lines:
                                        df_line_split = df_line.split()
                                        # ...and check if the line contains the necessary information
                                        if 6 >= len(df_line_split) > 1:
                                            # Extract capacity, used, available, and percentage from the 'df' output
                                            capacity, used, available, used_percent, mountpoint = df_line.split()[-5:]
                                            if capacity.isdigit() and used.isdigit() and available.isdigit():
                                                capacity = int(capacity) * 1024
                                                used = int(used) * 1024
                                                available = int(available) * 1024
                                                percentage = int((used / capacity) * 100)
                                                # Store the persistent volume information in the dictionary
                                                persistent_volumes[volume['persistentVolumeClaim']['claimName']] = {
                                                    'namespace': namespace,
                                                    'pvc': volume['persistentVolumeClaim']['claimName'],
                                                    'percentage': percentage,
                                                    'capacity': capacity,
                                                    'used': used,
                                                    'available': available}
                                # Add to already scanned mounts so not to scan them again
                                mounts_scanned.append(mount['name'])
    return persistent_volumes


def get_deployments(namespace_resources: dict) -> dict:
    """
    Get deployments in a namespace
    :param namespace_resources: Resources in the namespace
    :return: Dictionary of deployments
    """
    deployments = dict()
    # Filter deployment resources from the namespace resources
    deployments_resources = [x for x in namespace_resources['items'] if x['kind'] == 'Deployment']
    for deployment in deployments_resources:
        # Check if the deployment has necessary metadata and status information
        if deployment.get('metadata') and \
                deployment['metadata'].get('name') and \
                deployment.get('status') and \
                deployment['status'].get('replicas') and \
                (deployment['status'].get('readyReplicas') or
                 deployment['status'].get('unavailableReplicas')):
            # Store the deployment information in the dictionary
            deployments[deployment['metadata']['name']] = {
                'replicas': deployment['status']['replicas'],
                'ready_replicas': deployment['status'].get('readyReplicas', 0),
                'unavailable_replicas': deployment['status'].get('unavailableReplicas', 0)
            }
    return deployments


def get_daemonsets(namespace_resources: dict) -> dict:
    """
    Get daemonsets in a namespace
    :param namespace_resources: Resources in the namespace
    :return: Dictionary of daemonsets
    """
    daemonsets = dict()
    # Filter daemonset resources from the namespace resources
    daemonsets_resources = [x for x in namespace_resources['items'] if x['kind'] == 'DaemonSet']
    for daemonset in daemonsets_resources:
        # Check if the daemonset has necessary metadata and status information
        if daemonset.get('metadata') and \
                daemonset['metadata'].get('name') and \
                daemonset.get('status') and \
                daemonset['status'].get('currentNumberScheduled') and \
                (daemonset['status'].get('numberReady') or
                 daemonset['status'].get('numberUnavailable')):
            # Store the daemonset information in the dictionary
            daemonsets[daemonset['metadata']['name']] = {
                'current_number_scheduled': daemonset['status']['currentNumberScheduled'],
                'number_ready': daemonset['status'].get('numberReady', 0),
                'number_unavailable': daemonset['status'].get('numberUnavailable', 0),
                'desired_number_scheduled': daemonset['status'].get('desiredNumberScheduled', 0)
            }
    return daemonsets


def get_replicasets(namespace_resources: dict) -> dict:
    """
    Get replicasets in a namespace
    :param namespace_resources: Resources in the namespace
    :return: Dictionary of replicasets
    """
    replicasets = dict()
    # Filter replicaset resources from the namespace resources
    replicasets_resources = [x for x in namespace_resources['items'] if x['kind'] == 'ReplicaSet']
    for replicaset in replicasets_resources:
        # Check if replicaset is part of a deployment
        if replicaset.get('metadata') and \
                not replicaset['metadata'].get('ownerReferences') or \
                replicaset['metadata']['ownerReferences'][0].get('kind') != 'Deployment':
            # Check if replicaset has necessary metadata and status information
            if replicaset['metadata'].get('name') and \
                    replicaset.get('status') and \
                    replicaset['status'].get('replicas') and \
                    (replicaset['status'].get('readyReplicas') or
                     replicaset['status'].get('availableReplicas')):
                # Store the replicaset information in the dictionary
                replicasets[replicaset['metadata']['name']] = {
                    'replicas': replicaset['status']['replicas'],
                    'ready_replicas': replicaset['status'].get('readyReplicas', 0),
                    'available_replicas': replicaset['status'].get('availableReplicas', 0)
                }
    return replicasets


def get_cronjobs(namespace_resources: dict) -> dict:
    """
    Get cronjobs in a namespace
    :param namespace_resources: Resources in the namespace
    :return: Dictionary of cronjobs
    """
    cronjobs = dict()
    start_times = list()
    # Filter cronjob resources from the namespace resources
    cronjobs_resources = [x for x in namespace_resources['items'] if x['kind'] == 'CronJob']
    for cronjob in cronjobs_resources:
        # Check if the cronjob has necessary metadata and status information
        if cronjob.get('metadata') and \
                cronjob['metadata'].get('name') and \
                cronjob.get('status'):

            # Store the cronjob information in the dictionary
            cronjobs[cronjob['metadata']['name']] = {
                'active': len(cronjob['status'].get('active', []))
            }
    return cronjobs


def get_pods(namespace_resources: dict) -> dict:
    """
    Get pods in a namespace
    :param namespace_resources: Resources in the namespace
    :return: Dictionary of pods
    """
    pods = dict()
    # Filter pod resources from the namespace resources
    pods_resources = [x for x in namespace_resources['items'] if x['kind'] == 'Pod']
    for pod in pods_resources:
        # Check if the pod has necessary metadata information
        if pod.get('metadata') and \
                pod['metadata'].get('name'):
            # Initialize the pod's container states
            pods[pod['metadata']['name']] = {'containers': {'crashing': list(),
                                                            'running': list(),
                                                            'waiting': list(),
                                                            'terminated': list()}}

        # Check if the pod has status information and container statuses
        if pod.get('status') and \
                pod['status'].get('containerStatuses'):
            for container_status in pod['status']['containerStatuses']:
                if container_status.get('state'):
                    # Check if the container is in a waiting state
                    if container_status['state'].get('waiting'):
                        pods[pod['metadata']['name']]['containers']['waiting'].append(container_status.get('name'))
                        # Check if the container is crashing
                        if container_status['state']['waiting'].get('reason') == 'CrashLoopBackOff':
                            pods[pod['metadata']['name']]['containers']['crashing'].append(container_status.get('name'))
                    # Check if the container is in a running state
                    if container_status['state'].get('running'):
                        pods[pod['metadata']['name']]['containers']['running'].append(container_status.get('name'))
                    # Check if the container is in a terminated state
                    if container_status['state'].get('terminated'):
                        pods[pod['metadata']['name']]['containers']['terminated'].append(container_status.get('name'))
    return pods


if __name__ == '__main__':

    configure_plugin()

    # Get the kubectl binary path
    KUBECTL = get_kubectl_binary()

    # Initialize namespaces
    namespaces = {x: Namespace(x) for x in get_namespaces()}

    # Collect resources for each namespace
    for namespace in get_namespaces():
        namespace_resources = get_namespace_resources(namespace)
        namespaces[namespace].pods = get_pods(namespace_resources)
        namespaces[namespace].persistent_volumes = get_persistent_volumes(namespace_resources)
        namespaces[namespace].deployments = get_deployments(namespace_resources)
        namespaces[namespace].daemonsets = get_daemonsets(namespace_resources)
        namespaces[namespace].replicasets = get_replicasets(namespace_resources)
        namespaces[namespace].cronjobs = get_cronjobs(namespace_resources)

    # Print the collected namespace information
    print('<<<kubernetes_namespaces:sep(59)>>>')
    for namespace in namespaces:
        print(namespaces[namespace].as_dict())
