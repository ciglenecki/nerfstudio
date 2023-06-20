# Copyright 2022 the Regents of the University of California, Nerfstudio Team and contributors. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Evaluation utils
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal, Optional, Tuple

import torch
import yaml

from nerfstudio.configs.method_configs import all_methods
from nerfstudio.data.datamanagers.base_datamanager import VanillaDataManagerConfig
from nerfstudio.engine.trainer import TrainerConfig
from nerfstudio.pipelines.base_pipeline import Pipeline
from nerfstudio.utils.rich_utils import CONSOLE


def eval_load_checkpoint(config: TrainerConfig, pipeline: Pipeline) -> Tuple[Path, int]:
    ## TODO: ideally eventually want to get this to be the same as whatever is used to load train checkpoint too
    """Helper function to load checkpointed pipeline

    Args:
        config (DictConfig): Configuration of pipeline to load
        pipeline (Pipeline): Pipeline instance of which to load weights
    Returns:
        A tuple of the path to the loaded checkpoint and the step at which it was saved.
    """

    checkpoint_path = Path(config.load_ckpt)

    if checkpoint_path is None:
        CONSOLE.rule("Error", style="red")
        CONSOLE.print(f"Please pass the --load-ckpt <CKPT_PATH> argument.", justify="center")
        sys.exit(1)

    loaded_state = torch.load(checkpoint_path, map_location="cpu")

    if "step" not in loaded_state or not loaded_state["step"]:
        load_step = get_step_from_ckpt_path(checkpoint_path)
    else:
        load_step = loaded_state["step"]

    pipeline.load_pipeline(loaded_state["pipeline"], load_step)
    CONSOLE.print(f":white_check_mark: Done loading checkpoint from {str(checkpoint_path)}")
    return checkpoint_path, load_step


def eval_setup(
    config_path: Path,
    eval_num_rays_per_chunk: Optional[int] = None,
    test_mode: Literal["test", "val", "inference"] = "test",
    load_ckpt: Path | None = None,
    indices_file: Path | None = None,
) -> tuple[TrainerConfig, Pipeline, Path, int]:
    """Shared setup for loading a saved pipeline for evaluation.

    Args:
        config_path: Path to config YAML file.
        eval_num_rays_per_chunk: Number of rays per forward pass
        test_mode:
            'val': loads train/val datasets into memory
            'test': loads train/test dataset into memory
            'inference': does not load any dataset into memory


    Returns:
        Loaded config, pipeline module, corresponding checkpoint, and step
    """
    # load save config
    config = yaml.load(config_path.read_text(), Loader=yaml.Loader)
    assert isinstance(config, TrainerConfig)

    # TODO: matej, this is their weird line
    config.pipeline.datamanager._target = all_methods[config.method_name].pipeline.datamanager._target
    
    # load checkpointed information
    if load_ckpt is not None:
        config.load_ckpt = load_ckpt

    if indices_file is not None:
        config.pipeline.datamanager.dataparser.indices_file = indices_file

    if load_ckpt is not None and config.pipeline.datamanager.train_size_initial is None:
        state = Trainer.get_checkpoint_state(load_ckpt)
        train_size_initial = NerfactoModel.get_train_size_from_checkpoint(state)
        config.pipeline.datamanager.train_size_initial = train_size_initial

    if eval_num_rays_per_chunk:
        config.pipeline.model.eval_num_rays_per_chunk = eval_num_rays_per_chunk

    # load checkpoints from wherever they were saved
    # TODO: expose the ability to choose an arbitrary checkpoint
    
    # TODO: matej, my old line
    # config.pipeline.datamanager.eval_image_indices = None
    
    # TODO: their new lines
    config.load_dir = config.get_checkpoint_dir()
    if isinstance(config.pipeline.datamanager, VanillaDataManagerConfig):
        config.pipeline.datamanager.eval_image_indices = None

    # setup pipeline (which includes the DataManager)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pipeline = config.pipeline.setup(device=device, test_mode=test_mode)
    assert isinstance(pipeline, Pipeline)
    pipeline.eval()

    # load checkpointed information
    checkpoint_path, step = eval_load_checkpoint(config, pipeline)

    return config, pipeline, checkpoint_path, step
