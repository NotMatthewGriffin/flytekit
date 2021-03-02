import os
from typing import Any, Dict, List, Optional, Type

from flytekit.common.tasks.raw_container import _get_container_definition
from flytekit.core.base_task import PythonTask
from flytekit.core.context_manager import ExecutionState, FlyteContext, SerializationSettings
from flytekit.core.interface import transform_interface_to_list_interface
from flytekit.core.python_function_task import PythonFunctionTask, get_registerable_container_image
from flytekit.models.array_job import ArrayJob
from flytekit.models.interface import Variable
from flytekit.models.task import Container


class MapPythonTask(PythonTask):
    """
    TODO: support lambda functions
    """

    def __init__(
        self,
        python_function_task: PythonFunctionTask,
        concurrency: int = None,
        min_success_ratio: float = None,
        **kwargs,
    ):
        """
        :param task_function: This argument is implicitly passed and represents the repeatable function
        :param concurrency: If specified, this limits the number of mapped tasks than can run in parallel to the given
        batch size
        :param min_success_ratio: If specified, this determines the minimum fraction of total jobs which can complete
            successfully before terminating this task and marking it successful.
        """
        collection_interface = transform_interface_to_list_interface(python_function_task.python_interface)
        name = f"{python_function_task._task_function.__module__}.mapper_{python_function_task._task_function.__name__}"
        self._run_task = python_function_task
        self._max_concurrency = concurrency
        self._min_success_ratio = min_success_ratio
        self._array_task_interface = python_function_task.python_interface
        super().__init__(
            name=name,
            interface=collection_interface,
            task_type="container_array",
            task_config=None,
            task_type_version=1,
            **kwargs,
        )

    def get_command(self, settings: SerializationSettings) -> List[str]:
        return [
            "pyflyte-map-execute",
            "--task-module",
            self._run_task._task_function.__module__,
            "--task-name",
            f"{self._run_task._task_function.__name__}",
            "--inputs",
            "{{.input}}",
            "--output-prefix",
            "{{.outputPrefix}}",
            "--raw-output-data-prefix",
            "{{.rawOutputDataPrefix}}",
        ]

    def get_container(self, settings: SerializationSettings) -> Container:
        env = {**settings.env, **self.environment} if self.environment else settings.env
        return _get_container_definition(
            image=get_registerable_container_image(None, settings.image_config),
            command=[],
            args=self.get_command(settings=settings),
            data_loading_config=None,
            environment=env,
        )

    def get_custom(self, settings: SerializationSettings) -> Dict[str, Any]:
        return ArrayJob(parallelism=self._max_concurrency, min_success_ratio=self._min_success_ratio).to_dict()

    @property
    def run_task(self) -> PythonTask:
        return self._run_task

    def execute(self, **kwargs) -> Any:
        ctx = FlyteContext.current_context()
        if ctx.execution_state and ctx.execution_state.mode == ExecutionState.Mode.TASK_EXECUTION:
            return self._execute_map_task(ctx, **kwargs)

        return self._raw_execute(**kwargs)

    @staticmethod
    def _compute_array_job_index() -> int:
        """
        Computes the absolute index of the current array job. This is determined by summing the compute-environment-specific
        environment variable and the offset (if one's set). The offset will be set and used when the user request that the
        job runs in a number of slots less than the size of the input.
        """
        offset = 0
        if os.environ.get("BATCH_JOB_ARRAY_INDEX_OFFSET"):
            offset = int(os.environ.get("BATCH_JOB_ARRAY_INDEX_OFFSET"))
        return offset + int(os.environ.get(os.environ.get("BATCH_JOB_ARRAY_INDEX_VAR_NAME")))

    @property
    def _outputs_interface(self) -> Dict[Any, Variable]:
        """
        We override this method from PythonTask because the dispatch_execute method uses this
        interface to construct outputs. Each instance of an container_array task will however produce outputs
        according to the underlying run_task interface and the array plugin handler will actually create a collection
        from these individual outputs as the final output value.
        """

        ctx = FlyteContext.current_context()
        if ctx.execution_state is not None and ctx.execution_state.mode == ExecutionState.Mode.LOCAL_WORKFLOW_EXECUTION:
            # In workflow execution mode we actually need to use the parent (mapper) task output interface.
            return self.interface.outputs
        return self._run_task.interface.outputs

    def get_type_for_output_var(self, k: str, v: Any) -> Optional[Type[Any]]:
        """
        We override this method from flytekit.core.base_task Task because the dispatch_execute method uses this
        interface to construct outputs. Each instance of an container_array task will however produce outputs
        according to the underlying run_task interface and the array plugin handler will actually create a collection
        from these individual outputs as the final output value.
        """
        ctx = FlyteContext.current_context()
        if ctx.execution_state is not None and ctx.execution_state.mode == ExecutionState.Mode.LOCAL_WORKFLOW_EXECUTION:
            # In workflow execution mode we actually need to use the parent (mapper) task output interface.
            return self._python_interface.outputs[k]
        return self._run_task._python_interface.outputs[k]

    def _execute_map_task(self, ctx: FlyteContext, **kwargs) -> Any:
        """
        This is called during ExecutionState.Mode.TASK_EXECUTION executions, that is executions orchestrated by the
        Flyte platform. Individual instances of the map task, aka array task jobs are passed the full set of inputs but
        only produce a single output based on the map task (array task) instance. The array plugin handler will actually
        create a collection from these individual outputs as the final map task output value.
        """
        task_index = self._compute_array_job_index()
        map_task_inputs = {}
        for k in self.interface.inputs.keys():
            map_task_inputs[k] = kwargs[k][task_index]
        return self._run_task.execute(**map_task_inputs)

    def _raw_execute(self, **kwargs) -> Any:
        """
        This is called during locally run executions. Unlike array task execution on the Flyte platform, _raw_execute
        produces the full output collection.
        """
        outputs_expected = True
        if not self.interface.outputs:
            outputs_expected = False
        outputs = []
        for _ in self._outputs_interface.keys():
            outputs.append([])

        any_input_key = (
            list(self._run_task.interface.inputs.keys())[0]
            if self._run_task.interface.inputs.items() is not None
            else None
        )

        for i in range(len(kwargs[any_input_key])):
            single_instance_inputs = {}
            for k in self.interface.inputs.keys():
                single_instance_inputs[k] = kwargs[k][i]
            o = self._run_task.execute(**single_instance_inputs)
            if outputs_expected:
                for x in range(len(outputs)):
                    outputs[x].append(o[x])

        if len(outputs) == 1:
            return outputs[0]

        return tuple(outputs)


def maptask(task_function: PythonFunctionTask, concurrency: int = None, min_success_ratio: float = None, **kwargs):
    """
    Use a maptask for parallelizable tasks that are run across a List of an input type. A maptask can be composed of any
    individual :py:class:`flytekit.PythonFunctionTask`.

    Invoke a maptask with arguments using the :py:class:`list` version of the expected input. TODO this will one day
    change to tuples

    Usage:

    .. code-block:: python

        @task
        def my_mappable_task(a: int) -> str:
            return str(a)

        @workflows
        def my_wf(x: typing.List[int]) -> typing.List[str]:
             return maptask(my_mappable_task, metadata=TaskMetadata(retries=1), requests=Resources(cpu="10M"))(a=x)

    At run time, the underlying map task will be run for every value in the input collection. Task-specific attributes
    such as :py:class:`flytekit.TaskMetadata` and :py:class:`flytekit.Resources` are applied to individual instances
    of the mapped task.

    :param task_function: This argument is implicitly passed and represents the repeatable function
    :param concurrency: If specified, this limits the number of mapped tasks than can run in parallel to the given batch
        size
    :param min_success_ratio: If specified, this determines the minimum fraction of total jobs which can complete
        successfully before terminating this task and marking it successful.
    """
    if not isinstance(task_function, PythonFunctionTask):
        raise ValueError(
            f"Only Flyte python task types are supported in maptask currently, received {type(task_function)}"
        )
    # We could register in a global singleton here?
    return MapPythonTask(task_function, concurrency=concurrency, min_success_ratio=min_success_ratio, **kwargs)
