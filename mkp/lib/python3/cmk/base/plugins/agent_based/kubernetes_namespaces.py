# Server-side plugin for monitoring Kubernetes namespaces,
# resides at lib/python3/cmk/base/plugins/agent_based/kubernetes_namespaces.py
# ©2024 henri.wahl@ukdd.de

from datetime import datetime

from .agent_based_api.v1 import Metric, register, Result, Service, State

# separates Kubernetes resources in the item name
SEPARATOR = ' / '
# list of Kubernetes objects that are simplified, like pods, which are not looked at in every detail
SIMPLE_KUBERNETES_OBJECTS = ['pods']
# time string for non-existing time in CronJob objects
TIME_ZERO = '1970-01-01T00:00:00Z'


def bytes_to_human_readable(bytes: int) -> str:
    """
    Convert bytes to a human-readable string format.

    :param bytes: Number of bytes.
    :return: Human-readable string representation of the bytes.
    """
    # just in case
    bytes = int(bytes)
    if bytes < 1024:
        return f'{bytes} B'
    elif bytes < 1024 ** 2:
        return f'{bytes / 1024:.2f} KB'
    elif bytes < 1024 ** 3:
        return f'{bytes / 1024 ** 2:.2f} MB'
    elif bytes < 1024 ** 4:
        return f'{bytes / 1024 ** 3:.2f} GB'
    else:
        return f'{bytes / 1024 ** 4:.2f} TB'


def parse_kubernetes_namespaces(string_table):
    """
    Parse the Kubernetes namespaces from the given string table in agent output

    :param string_table: List of Checkmk items
    :return: List of parsed lines.
    """
    parsed_lines = []
    # string_table cames in raw text format, resembling Python dictionaries
    for line in string_table:
        if len(line) > 0:
            try:
                # eval() is used to convert the string to a real dictionary
                parsed_lines.append(eval(line[0]))
            except Exception as exception:
                print(exception)
    return parsed_lines


def discover_kubernetes_namespaces(section):
    """
    Discover Kubernetes namespaces from the given section.

    :param section: Section containing namespace information.
    :yield: Service objects for each discovered namespace.
    """
    # Iterate over each group in the section
    for group in section:
        # Ensure the group is not 'check_mk' and is a dictionary with a 'name' key
        if group != 'check_mk' and \
                isinstance(group, dict) and \
                group.get('name'):
            # Iterate over each Kubernetes object in the group
            for kubernetes_object_name, kubernetes_object in group.items():
                if kubernetes_object_name != 'name':
                    # If the Kubernetes object is not in the simplified list, iterate over its details
                    if not kubernetes_object_name in SIMPLE_KUBERNETES_OBJECTS:
                        for kubernetes_object_detail_name, kubernetes_object_detail in kubernetes_object.items():
                            # Yield a Service object for each detailed Kubernetes object
                            yield Service(item=SEPARATOR.join(
                                [group['name'], kubernetes_object_name, kubernetes_object_detail_name]))
                    else:
                        # Yield a Service object for simplified Kubernetes objects
                        if kubernetes_object:
                            yield Service(item=SEPARATOR.join([group['name'], kubernetes_object_name]))


def check_kubernetes_namespaces(item, params, section):
    """
    Check the status of Kubernetes namespaces.

    :param item: Item to check.
    :param params: Parameters for the check.
    :param section: Section containing namespace information.
    :yield: Result and Metric objects for the check.
    """
    # Extract namespace and resource names from the item, separated by SEPARATOR
    # e.g. from 'kube-system / deployments / local-path-provisioner'
    namespace_name = item.split(SEPARATOR)[0]
    resource_name = item.split(SEPARATOR)[-1]

    # Get warning and critical thresholds for persistent volumes and cronjob age
    percentage_persistent_volumes_warning, percentage_persistent_volumes_critical = params.get(
        'percentage_persistent_volumes')
    threshold_cronjob_count_warning, threshold_cronjob_count_critical = params.get(
        'threshold_cronjob_count')

    # Filter the section to find the namespace
    namespace_list = [x for x in section if x.get('name') == namespace_name]

    if namespace_list:
        namespace = namespace_list[0]
        # Iterate over each Kubernetes object in the namespace
        for kubernetes_object_name, kubernetes_object in namespace.items():
            if kubernetes_object_name != 'name':
                # Determine the Kubernetes object from the item...
                # ...if it should get less details like pods, which are summed up like
                # 'cert-manager / pods'
                if kubernetes_object_name in SIMPLE_KUBERNETES_OBJECTS:
                    kubernetes_object_from_item = item.split(SEPARATOR)[-1]
                # ...or if it should get more details like deployments, which look like
                # 'cert-manager / deployments / cert-manager'
                else:
                    kubernetes_object_from_item = item.split(SEPARATOR)[-2]
                # If the Kubernetes object matches the one from the item we go further
                if kubernetes_object_name == kubernetes_object_from_item:
                    if not namespace.get(kubernetes_object_name):
                        continue
                    # Default settings for summary and state
                    # These values will be changed by the following actions and are used for the final result
                    summary = f'{kubernetes_object}'
                    state = State.OK

                    # Single name of the Kubernetes object like name of a CronJob
                    kubernetes_object_single_name = item.split(SEPARATOR)[-1]

                    # Check the status of pods
                    if kubernetes_object_name == 'pods':
                        crashing = 0
                        running = 0
                        terminated = 0
                        waiting = 0
                        for pod in kubernetes_object.values():
                            containers = pod.get('containers')
                            if containers:
                                # variuos pod states are summed up for a final summary
                                crashing += len(containers.get('crashing', []))
                                running += len(containers.get('running', []))
                                terminated += len(containers.get('terminated', []))
                                waiting += len(containers.get('waiting', []))
                        summary = f'running: {running}, waiting: {waiting}, terminated: {terminated}, crashing: {crashing}'
                        # crashing pods are critical
                        if crashing > 0:
                            state = State.CRIT

                        # Metrics are yielded for the graphs
                        yield Metric('pods_running', running)
                        yield Metric('pods_waiting', waiting)
                        yield Metric('pods_crashing', crashing)
                        yield Metric('pods_terminated', terminated)

                    # Check the status of deployments
                    if kubernetes_object_name == 'deployments':
                        replicas = 0
                        ready_replicas = 0
                        unavailable_replicas = 0
                        for deployment in kubernetes_object.values():
                            replicas += deployment.get('replicas', 0)
                            ready_replicas += deployment.get('ready_replicas', 0)
                            unavailable_replicas += deployment.get('unavailable_replicas', 0)
                        summary = f'replicas: {replicas}, ready: {ready_replicas}, unavailable: {unavailable_replicas}'
                        # if not all replicas are ready, it is a critical state
                        if replicas != ready_replicas:
                            state = State.CRIT

                        # Metrics are yielded for the graphs
                        yield Metric('deployments_replicas', replicas)
                        yield Metric('deployments_ready_replicas', ready_replicas)
                        yield Metric('deployments_unavailable_replicas', unavailable_replicas)

                    # Check the status of daemonsets
                    if kubernetes_object_name == 'daemonsets':
                        current_number_scheduled = 0
                        desired_number_scheduled = 0
                        number_ready = 0
                        number_unavailable = 0
                        for daemonset in kubernetes_object.values():
                            current_number_scheduled += daemonset.get('current_number_scheduled', 0)
                            desired_number_scheduled += daemonset.get('desired_number_scheduled', 0)
                            number_ready += daemonset.get('number_ready', 0)
                            number_unavailable += daemonset.get('number_unavailable', 0)
                        summary = f'current: {current_number_scheduled}, desired: {desired_number_scheduled}, ready: {number_ready}, unavailable: {number_unavailable}'

                        # DaemonSets are critical if not all are ready
                        if number_unavailable > 0:
                            state = State.CRIT

                        # Metrics are yielded for the graphs
                        yield Metric('daemonsets_current_number_scheduled', current_number_scheduled)
                        yield Metric('daemonsets_desired_number_scheduled', desired_number_scheduled)
                        yield Metric('daemonsets_number_ready', number_ready)
                        yield Metric('daemonsets_number_unavailable', number_unavailable)

                    # Check the status of replicasets
                    if kubernetes_object_name == 'replicasets':
                        replicas = 0
                        ready_replicas = 0
                        unavailable_replicas = 0
                        for replicaset in kubernetes_object.values():
                            replicas += replicaset.get('replicas', 0)
                            ready_replicas += replicaset.get('ready_replicas', 0)
                            unavailable_replicas += replicaset.get('unavailable_replicas', 0)
                        summary = f'replicas: {replicas}, ready: {ready_replicas}, unavailable: {unavailable_replicas}'

                        # If not all replicas are ready, it is a critical state
                        if replicas != ready_replicas:
                            state = State.CRIT

                        # Metrics are yielded for the graphs
                        yield Metric('replicasets_replicas', replicas)
                        yield Metric('replicasets_ready_replicas', ready_replicas)
                        yield Metric('replicasets_unavailable_replicas', unavailable_replicas)

                    # Check the status of cronjobs
                    if kubernetes_object_name == 'cronjobs':
                        cronjob = kubernetes_object.get(kubernetes_object_single_name, {})
                        active = cronjob.get('active', 0)
                        # When too many CronJobs are active something is wrong
                        if active >= threshold_cronjob_count_warning:
                            state = State.WARN
                        if active >= threshold_cronjob_count_critical:
                            state = State.CRIT

                        summary = f'active: {active}'

                        # Metrics are yielded for the graphs
                        yield Metric('cronjobs_active', active)

                    # Check the status of persistent volumes
                    if kubernetes_object_name == 'persistent_volumes':
                        if kubernetes_object.get(resource_name):
                            persistent_volume = kubernetes_object.get(resource_name)
                            capacity = persistent_volume.get('capacity', 0)
                            used = persistent_volume.get('used', 0)
                            percentage = persistent_volume.get('percentage', 0)
                            summary = f'used: {bytes_to_human_readable(used)} capacity: {bytes_to_human_readable(capacity)} percentage: {percentage} %'

                            # If the percentage of the persistent volume is higher than the thresholds,
                            # it is a warning or critical state
                            if percentage > percentage_persistent_volumes_warning:
                                state = State.WARN
                            if percentage > percentage_persistent_volumes_critical:
                                state = State.CRIT

                            # Metrics are yielded for the graphs
                            yield Metric(name='persistent_volume_used',
                                         value=used,
                                         boundaries=(0.0, capacity))
                            yield Metric(name='persistent_volume_capacity',
                                         value=capacity,
                                         boundaries=(0.0, capacity))
                            yield Metric(name='persistent_volume_percentage',
                                         value=percentage,
                                         levels=(
                                             percentage_persistent_volumes_warning,
                                             percentage_persistent_volumes_critical),
                                         boundaries=(0.0, 100.0))

                    # Yield the result for the current Kubernetes object
                    yield Result(state=state, summary=summary)


register.agent_section(
    name='kubernetes_namespaces',
    parse_function=parse_kubernetes_namespaces,
)

register.check_plugin(
    name='kubernetes_namespaces',
    sections=['kubernetes_namespaces'],
    service_name='K8s %s',
    discovery_function=discover_kubernetes_namespaces,
    check_function=check_kubernetes_namespaces,
    check_default_parameters={'percentage_persistent_volumes': (80.0, 90.0),
                              'threshold_cronjob_count': (2, 3)},
    check_ruleset_name='kubernetes_namespaces'
)
