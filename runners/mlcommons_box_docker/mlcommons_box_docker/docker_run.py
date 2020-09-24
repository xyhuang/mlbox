import os
import logging
import typing

from mlcommons_box.common import mlbox_metadata
from mlcommons_box.runner.objects import platform_config


from mlcommons_box_docker import metadata


logger = logging.getLogger(__name__)


class DockerRun(object):
    def __init__(self,
                 mlbox: mlbox_metadata.MLBox,
                 runner_config: platform_config.RunnerConfig):
        """Docker Runner.
        Args:
            mlbox: MLBox specification.
            runner_config: Runner configuration built from the box's and the
                    user's platform config files.
        """
        self.mlbox: mlbox_metadata.MLBox = mlbox
        self.runner_config: platform_config.RunnerConfig = runner_config
        # make sure only supported exec interfaces are used
        if self.runner_config.exec.type != "container":
            raise ValueError('Exec type must be "container".')

    def configure(self):
        """Build Docker Image on a current host."""
        image_name: str = self.runner_config.exec.container.image

        # According to MLBox specs (?), build directory is {mlbox.root}/build that contains all files to build MLBox.
        # Dockerfiles are built taking into account that {mlbox.root}/build is the context (build) directory.
        build_path: str = self.mlbox.build_path
        docker_file: str = os.path.join(build_path, 'Dockerfile')
        if not os.path.exists(docker_file):
            raise RuntimeError(f"Docker file not found: {docker_file}")

        env_args = ' '.join([f"-e {env_var.name}={env_var.value}" for env_var in
                             self.runner_config.exec.container.env])

        cmd: str = f"cd {build_path}; docker build {env_args} -t {image_name} -f Dockerfile ."
        logger.info(cmd)
        self._run_or_die(cmd)

    def run(self):
        """Run a box."""
        # The 'mounts' dictionary maps host path to container path
        mounts, args = self._generate_mounts_and_args()
        print(f"mounts={mounts}, args={args}")

        volumes_str = ' '.join(['--volume {}:{}'.format(t[0], t[1]) for t in mounts.items()])
        image_name: str = self.runner_config.exec.container.image
        runtime = self.runner_config.exec.container.runtime
        runtime_arg = f"--runtime={runtime}" if runtime else ""
        env_args = ' '.join([f"-e {env_var.name}={env_var.value}" for env_var in
                             self.runner_config.exec.container.env])

        args = ' '.join(args)
        cmd = f"docker run --rm {runtime_arg} {volumes_str} {env_args} {image_name} {args}"
        logger.info(cmd)
        self._run_or_die(cmd)

    def _generate_mounts_and_args(self) -> typing.Tuple[dict, list]:
        mounts, args = {}, [self.mlbox.invoke.task_name]

        def _create(binding_: dict, input_specs_: dict):
            # name: parameter name, path: parameter value
            for name, path in binding_.items():
                path = path.replace('$WORKSPACE', self.mlbox.workspace_path)

                path_type = input_specs_[name]
                if path_type == 'directory':
                    os.makedirs(path, exist_ok=True)
                    mounts[path] = mounts.get(
                        path,
                        '/mlbox_io{}/{}'.format(len(mounts), os.path.basename(path))
                    )
                    args.append('--{}={}'.format(name, mounts[path]))
                elif path_type == 'file':
                    file_path, file_name = os.path.split(path)
                    os.makedirs(file_path, exist_ok=True)
                    mounts[file_path] = mounts.get(
                        file_path,
                        '/mlbox_io{}/{}'.format(len(mounts), file_path)
                    )
                    args.append('--{}={}'.format(name, mounts[file_path] + '/' + file_name))
                else:
                    raise RuntimeError(f"Invalid path type: '{path_type}'")

        _create(self.mlbox.invoke.input_binding, self.mlbox.task.inputs)
        _create(self.mlbox.invoke.output_binding, self.mlbox.task.outputs)

        return mounts, args

    def _run_or_die(self, cmd):
        print(cmd)
        if os.system(cmd) != 0:
            raise Exception('Command failed: {}'.format(cmd))
