# Server-side WATO settings for plugin for monitoring Kubernetes namespaces,
# resides at share/check_mk/web/plugins/wato/kubernetes_namespaces.py
# ©2024 henri.wahl@ukdd.de

from cmk.gui.i18n import _

from cmk.gui.valuespec import (
    Dictionary,
    FixedValue,
    Integer,
    ListOf,
    Percentage,
    TextAscii,
    TextInput,
    Tuple
)

from cmk.gui.plugins.wato.utils import (
    CheckParameterRulespecWithItem,
    rulespec_registry,
    HostRulespec,
    RulespecGroupCheckParametersApplications,
    RulespecGroupCheckParametersDiscovery
)


def _item_kubernetes_namespaces() -> TextInput:
    """
    Define the item specification for Kubernetes namespaces.

    :return: TextInput object for Kubernetes namespaces.
    """
    return TextInput(
        title='Kubernetes namespaces',
        help='Settings for Kubernetes namespaces',
    )


def _valuespec_kubernetes_namespaces() -> Dictionary:
    """
    Define the value specification for Kubernetes namespaces in the Web GUI.

    :return: Dictionary object containing value specifications.
    """
    return Dictionary(
        title=_('Kubernetes namespaces'),
        elements=[('kubernetes_namespaces',
                   ListOf(
                       valuespec=Dictionary(
                           title=_('Kubernetes namespaces'),
                           elements=[
                               ('namespace',
                                TextAscii(
                                    title=_('Namespace'),
                                    label=_('Namespace'),
                                    default_value='',
                                    help=_(
                                        'Apply only to this namespace - if not used, the resources settings appliy to all namespaces'),
                                    size=30
                                )
                                ),
                               # FixedValue for CronJobs discovery
                               (
                                   'cronjobs',
                                   FixedValue(
                                       title=_('Cronjobs'),
                                       value=True,
                                       totext='Discover CronJobs',
                                       help=_('When enabled, discover CronJobs'),
                                   ),
                               ),
                               # FixedValue for DaemonSets discovery
                               (
                                   'daemonsets',
                                   FixedValue(
                                       title=_('DaemonSets'),
                                       value=True,
                                       totext='Discover DaemonSets',
                                       help=_('When enabled, discover DaemonSets'),
                                   ),
                               ),
                               # FixedValue for Deployments discovery
                               (
                                   'deployments',
                                   FixedValue(
                                       title=_('Deployments'),
                                       value=True,
                                       totext='Discover Deployments',
                                       help=_('When enabled, discover Deployments'),
                                   ),
                               ),
                               # FixedValue for PersistentVolumes discovery
                               (
                                   'persistent_volumes',
                                   FixedValue(
                                       title=_('PersistentVolumes'),
                                       value=True,
                                       totext='Discover Deployments',
                                       help=_('When enabled, discover PersistentVolumes'),
                                   ),
                               ),
                               # FixedValue for Pods discovery
                               (
                                   'pods',
                                   FixedValue(
                                       title=_('Pods'),
                                       value=True,
                                       totext='Discover Pods',
                                       help=_('When enabled, discover Pods'),
                                   ),
                               ),
                               # FixedValue for ReplicaSets discovery
                               (
                                   'replicasets',
                                   FixedValue(
                                       title=_('ReplicaSets'),
                                       value=True,
                                       totext='Discover ReplicaSets',
                                       help=_('When enabled, discover ReplicaSets'),
                                   ),
                               ),
                           ],
                           default_keys=['cronjobs',
                                         'daemonsets',
                                         'deployments',
                                         'replicasets',
                                         'persistent_volumes',
                                         'pods'],
                       ),
                       title=_('Kubernetes namespaces'),
                       help=_('Settings for Kubernetes namespaces'),
                       add_label=_('Add namespace')
                   )
                   )
                  ]
    )


def _parameter_kubernetes_namespaces() -> Dictionary:
    """
    Define the parameter specification for Kubernetes namespaces in Web GUI.

    :return: Dictionary object containing parameter specifications.
    """
    return Dictionary(
        elements=[
            # Define the percentage thresholds for persistent volumes
            ('percentage_persistent_volumes',
             Tuple(
                 title=_("Percentage threshold for persistent volumes "),
                 elements=[
                     Percentage(title=_('Warning'), default_value=80.0),
                     Percentage(title=_('Critical'), default_value=90.0),
                 ],
                 help=_('Set the percentage thresholds for persistent volumes')
             )
             ),
            # Define the threshold for CronJob count
            ('threshold_cronjob_count',
             Tuple(
                 title=_("Threshold for CronJob count"),
                 elements=[
                     Integer(title=_('Warning'), default_value=2, unit='count'),
                     Integer(title=_('Critical'), default_value=3, unit='count'),
                 ],
                 help=_('Set the threshold for CronJob count')
             )
             )
        ]
    )


# Register the rulespec for Kubernetes namespaces
rulespec_registry.register(
    CheckParameterRulespecWithItem(
        check_group_name='kubernetes_namespaces',
        group=RulespecGroupCheckParametersApplications,
        match_type='dict',
        item_spec=_item_kubernetes_namespaces,
        parameter_valuespec=_parameter_kubernetes_namespaces,
        title=lambda: _('Kubernetes namespaces'),
    )
)

# Register the rulespec for Kubernetes namespaces discovery
rulespec_registry.register(
    HostRulespec(
        group=RulespecGroupCheckParametersDiscovery,
        name="kubernetes_namespaces",
        valuespec=_valuespec_kubernetes_namespaces,
    )
)
