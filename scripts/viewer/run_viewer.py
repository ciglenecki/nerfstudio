#!/usr/bin/env python
"""
Starts viewer in eval mode.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Literal, Optional, Tuple

import tyro
from rich.console import Console
from scripts.my_utils import get_step_from_ckpt_path

from nerfstudio.configs.base_config import ViewerConfig
from nerfstudio.configs.method_configs import AnnotatedBaseConfigUnion
from nerfstudio.defaults import SPLIT_MODE_ALL
from nerfstudio.engine.trainer import TrainerConfig
from nerfstudio.pipelines.base_pipeline import Pipeline
from nerfstudio.utils import writer
from nerfstudio.utils.eval_utils import eval_setup
from nerfstudio.utils.writer import EventName, TimeWriter
from nerfstudio.viewer.server import viewer_utils

CONSOLE = Console(width=120, no_color=True)


@dataclass
class ViewerConfigWithoutNumRays(ViewerConfig):
    """Configuration for viewer instantiation"""

    num_rays_per_chunk: tyro.conf.Suppress[int] = -1
    start_train: tyro.conf.Suppress[bool] = False

    def as_viewer_config(self):
        """Converts the instance to ViewerConfig"""
        return ViewerConfig(**{x.name: getattr(self, x.name) for x in fields(self)})


@dataclass
class RunViewer:
    """Load a checkpoint and start the viewer."""

    load_config: Path
    """Path to config YAML file."""
    load_ckpt: Optional[Path] = None
    """Model checkpoint"""
    viewer: ViewerConfigWithoutNumRays = field(
        default_factory=ViewerConfigWithoutNumRays
    )
    indices_file: Optional[Path] = None
    """Viewer configuration"""
    dataset_type: Literal["train", "val", "all"] = "val"

    def main(self) -> None:
        """Main function."""
        if self.indices_file is not None:
            self.dataset_type = "all"
            CONSOLE.log("Setting dataset_type to 'all' because of indices file.")

        config, pipeline, _ = eval_setup(
            self.load_config,
            eval_num_rays_per_chunk=None,
            test_mode="test",
            load_ckpt=self.load_ckpt,
            indices_file=self.indices_file,
        )

        num_rays_per_chunk = config.viewer.num_rays_per_chunk
        assert self.viewer.num_rays_per_chunk == -1
        config.vis = "viewer"
        config.viewer = self.viewer.as_viewer_config()
        config.viewer.num_rays_per_chunk = num_rays_per_chunk

        self._start_viewer(config, pipeline)

    def _start_viewer(self, config: TrainerConfig, pipeline):
        base_dir = config.get_base_dir()
        viewer_log_path = base_dir / config.viewer.relative_log_filename
        viewer_state, banner_messages = viewer_utils.setup_viewer(
            config.viewer,
            log_filename=viewer_log_path,
            datapath=config.pipeline.datamanager.dataparser.data,
        )

        # We don't need logging, but writer.GLOBAL_BUFFER needs to be populated
        config.logging.local_writer.enable = False
        writer.setup_local_writer(
            config.logging,
            max_iter=config.max_num_iterations,
            banner_messages=banner_messages,
        )

        viewer_state.vis["renderingState/config_base_dir"].write(
            str(config.relative_model_dir)
        )

        viewer_state.vis["renderingState/export_path"].write(
            f"export-{config.pipeline.datamanager.dataparser.data.stem}_step_{get_step_from_ckpt_path(config.load_ckpt)}".replace(
                ".", "_"
            )
        )

        # TODO matej
        dataset_map = {
            "train": pipeline.datamanager.train_dataset,
            "val": pipeline.datamanager.eval_dataset,
            SPLIT_MODE_ALL: pipeline.datamanager.full_dataset,
        }

        assert viewer_state and dataset_map[self.dataset_type]
        viewer_state.init_scene(
            dataset=dataset_map[self.dataset_type],
            start_train=False,
        )

        while True:
            viewer_state.vis["renderingState/isTraining"].write(False)
            self._update_viewer_state(viewer_state, config, pipeline)

    def _update_viewer_state(
        self,
        viewer_state: viewer_utils.ViewerState,
        config: TrainerConfig,
        pipeline: Pipeline,
    ):
        """Updates the viewer state by rendering out scene with current pipeline
        Returns the time taken to render scene.

        """
        # NOTE: step must be > 0 otherwise the rendering would not happen
        step = 1
        num_rays_per_batch = config.pipeline.datamanager.train_num_rays_per_batch
        with TimeWriter(writer, EventName.ITER_VIS_TIME) as _:
            try:
                viewer_state.update_scene(
                    self, step, pipeline.model, num_rays_per_batch
                )
            except RuntimeError:
                time.sleep(0.03)  # sleep to allow buffer to reset
                assert viewer_state.vis is not None
                viewer_state.vis["renderingState/log_errors"].write(
                    "Error: GPU out of memory. Reduce resolution to prevent viewer from crashing."
                )

    def save_checkpoint(self, *args, **kwargs):
        """
        Mock method because we pass this instance to viewer_state.update_scene
        """


def entrypoint():
    """Entrypoint for use with pyproject scripts."""
    tyro.extras.set_accent_color("bright_yellow")
    tyro.cli(RunViewer).main()


if __name__ == "__main__":
    entrypoint()

# For sphinx docs
get_parser_fn = lambda: tyro.extras.get_parser(RunViewer)  # noqa
