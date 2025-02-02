"""
=====================
Remote Access
=====================

.. currentmodule:: flytekit.remote

This module provides utilities for performing operations on tasks, workflows, launchplans, and executions, for example,
the following code fetches and executes a workflow:

.. code-block:: python

    # create a remote object from flyte config and environment variables
    remote = FlyteRemote.from_config()

    # fetch a workflow from the flyte backend
    flyte_workflow = remote.fetch_workflow(name="my_workflow", version="v1")

    # execute the workflow, wait=True will return the execution object after it's completed
    workflow_execution = remote.execute(flyte_workflow, inputs={"a": 1, "b": 10}, wait=True)

    # inspect the execution's outputs
    print(workflow_execution.outputs)

.. _remote-entrypoint:

Entrypoint
==========

.. autosummary::
   :template: custom.rst
   :toctree: generated/
   :nosignatures:

   ~remote.FlyteRemote

.. _remote-flyte-entities:

Entities
========

.. autosummary::
   :template: custom.rst
   :toctree: generated/
   :nosignatures:

   ~tasks.task.FlyteTask
   ~workflow.FlyteWorkflow
   ~launch_plan.FlyteLaunchPlan

.. _remote-flyte-entity-components:

Entity Components
=================

.. autosummary::
   :template: custom.rst
   :toctree: generated/
   :nosignatures:

   ~nodes.FlyteNode
   ~component_nodes.FlyteTaskNode
   ~component_nodes.FlyteWorkflowNode

.. _remote-flyte-execution-objects:

Execution Objects
=================

.. autosummary::
   :template: custom.rst
   :toctree: generated/
   :nosignatures:

   ~workflow_execution.FlyteWorkflowExecution
   ~tasks.executions.FlyteTaskExecution
   ~nodes.FlyteNodeExecution

"""

from flytekit.remote.component_nodes import FlyteTaskNode, FlyteWorkflowNode
from flytekit.remote.executions import FlyteNodeExecution, FlyteTaskExecution, FlyteWorkflowExecution
from flytekit.remote.launch_plan import FlyteLaunchPlan
from flytekit.remote.nodes import FlyteNode
from flytekit.remote.remote import FlyteRemote
from flytekit.remote.task import FlyteTask
from flytekit.remote.workflow import FlyteWorkflow
