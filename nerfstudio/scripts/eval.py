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

#!/usr/bin/env python
"""
eval.py
"""
from __future__ import annotations

import gc
import json
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
import tyro

from nerfstudio.scripts.my_utils import (
    get_sequence_size_from_experiment,
    get_step_from_ckpt_path,
)
from nerfstudio.utils.colormaps import SceneDiverged
from nerfstudio.utils.eval_utils import eval_setup
from nerfstudio.utils.rich_utils import CONSOLE


@dataclass
class ComputePSNR:
    """Load a checkpoint, compute some PSNR metrics, and save it to a JSON file."""

    # Path to config YAML file.
    load_config: Path
    # Checkpoint path
    experiment_suffix: str
    load_ckpt: Path
    # Name of the output file.
    output_path: Path = Path("output.json")

    def main(self) -> None:
        """Main function."""
        for split in ["val", "test"]:
            # TODO: edit test mode to "test" and "eval" to aggregate results
            config, pipeline, checkpoint_path, _ = eval_setup(
                self.load_config,
                test_mode=split,
                load_ckpt=self.load_ckpt,
                indices_file=None,
            )
            out_name = f"{checkpoint_path.stem}_metrics_{split}_{self.experiment_suffix}_strictbox.json"
            self.output_path = Path(self.load_ckpt.parent, out_name)
            assert self.output_path.suffix == ".json"
            self.output_path.parent.mkdir(parents=True, exist_ok=True)

            step = get_step_from_ckpt_path(checkpoint_path)
            sequence_size = (
                get_sequence_size_from_experiment(config.experiment_name) if "_n_" in config.experiment_name else None
            )

            benchmark_info = {
                "experiment_name": config.experiment_name,
                "step": step,
                "sequence_size": sequence_size,
                "method_name": config.method_name,
                "checkpoint_path": str(checkpoint_path),
            }

            scene_diverged = False
            try:  # Get the output and define the names to save to
                metrics_dict: dict[str, dict[str, Any]] = pipeline.get_average_eval_image_metrics(agg_only=False)
                benchmark_info.update(metrics_dict)
            except SceneDiverged as e:
                traceback.print_exc()
                print(e)
                scene_diverged = True

            benchmark_info.update({"scene_diverged": scene_diverged})
            # Save output to output file
            self.output_path.write_text(json.dumps(benchmark_info, indent=4), "utf8")
            CONSOLE.print(f"Saved results to: {self.output_path}")

            del pipeline
            del config
            del benchmark_info
            del metrics_dict
            torch.cuda.empty_cache()
            gc.collect()
            time.sleep(3)


def entrypoint():
    """Entrypoint for use with pyproject scripts."""
    tyro.extras.set_accent_color("bright_yellow")
    tyro.cli(ComputePSNR).main()


if __name__ == "__main__":
    entrypoint()

# For sphinx docs
get_parser_fn = lambda: tyro.extras.get_parser(ComputePSNR)  # noqa
