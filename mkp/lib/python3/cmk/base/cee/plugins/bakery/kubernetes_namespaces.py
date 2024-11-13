# Server-side bakery part of plugin for monitoring Kubernetes namespaces
# Bakery definition at lib/python3/cmk/base/cee/plugins/bakery/kubernetes_namespaces.py
# inspired by https://exchange.checkmk.com/p/hello-bakery and
# https://github.com/mschlenker/checkmk-snippets/tree/main/mkp/hellobakery
# ©2024 henri.wahl@ukdd.de

from pathlib import Path
from typing import TypedDict, List

# Import API code
from .bakery_api.v1 import (FileGenerator,
                            OS,
                            Plugin,
                            PluginConfig,
                            register)


class KubernetesNamespacesConfig(TypedDict, total=False):
    """
    Configuration class for Kubernetes Namespaces plugin.
    """
    interval: int


def get_kubernetes_namespaces_plugin_files(conf: KubernetesNamespacesConfig) -> FileGenerator:
    """
    Generate the plugin files for Kubernetes Namespaces.

    :param conf: Configuration dictionary for the plugin.
    :return: Generator yielding Plugin objects.
    """
    # settings from WATO
    interval = conf.get('interval')

    # plugin script
    yield Plugin(
        base_os=OS.LINUX,
        source=Path('kubernetes_namespaces.py'),
        interval=interval)
    if 'kubeconfig_path' in conf:
        yield PluginConfig(base_os=OS.LINUX,
                           lines=[f"KUBECONFIG={conf['kubeconfig_path']}"],
                           target=Path("kubernetes_namespaces.cfg"),
                           include_header=True)


register.bakery_plugin(
    name='kubernetes_namespaces',
    files_function=get_kubernetes_namespaces_plugin_files
)
