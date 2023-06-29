import json
import random
import re
import sys
from datetime import datetime
from pathlib import Path, PurePath

import yaml


def get_n_from_dir_name(dir_name: str | Path) -> float | None:
    azimuth_pattern = r"n_([\d.]+)"
    if isinstance(dir_name, Path):
        dir_name = str(dir_name)
    match = re.search(azimuth_pattern, dir_name)
    if not match:
        return None
    return int(match.group(1))


def get_azimuth_from_dir_name(dir_name: str | Path) -> float | None:
    azimuth_pattern = r"azi_(-?\d+\.\d+)"
    if isinstance(dir_name, Path):
        dir_name = str(dir_name)
    match = re.search(azimuth_pattern, dir_name)
    if not match:
        return None
    return float(match.group(1))


def get_angle_from_dir_name(dir_name: str | Path) -> float | None:
    angle_pattern = r"a_([\d.]+)"
    if isinstance(dir_name, Path):
        dir_name = str(dir_name)
    match = re.search(angle_pattern, dir_name)
    if not match:
        return None
    return float(match.group(1))


def metrics_agg_by_angle(image_metrics: dict[str, dict[str, float]]) -> dict:
    result = {}
    metrics = list(image_metrics.values())[0].keys()
    for img_path, metric_dict in image_metrics.items():
        angle = get_azimuth_from_dir_name(img_path)
        if angle not in result:
            result[angle] = {"images": []}
        result[angle]["images"].append(img_path)
        for metric in metrics:
            metric_value = metric_dict[metric]
            if metric not in result[angle]:
                result[angle][metric] = []
            result[angle][metric].append(metric_value)
    for angle in result:
        for metric in metrics:
            result[angle][metric] = sum(result[angle][metric]) / len(result[angle][metric])
    print(json.dumps(result, indent=4))
    return result


def get_timestamp():
    return datetime.today().strftime("%Y-%m-%d-%H-%M-%S")


def random_codeword():
    """ac53"""
    letters = random.sample(string.ascii_lowercase, 2)
    word = "".join(letters)
    return f"{word}{random.randint(10, 99)}"


def get_experiment_name(timestamp=None, codeword=None):
    timestamp = timestamp if timestamp else get_timestamp()
    codeword = codeword if codeword else random_codeword()
    return f"{timestamp}-{codeword}"


class SocketConcatenator(object):
    def __init__(self, *files):
        self.files = files

    def write(self, obj):
        for f in self.files:
            f.write(obj)
        self.flush()

    def flush(self):
        for f in self.files:
            f.flush()


def stdout_to_file(file: Path):
    """
    Pipes standard input to standard input and to a file.
    """
    print("Standard output and errors piped to file:")
    f = open(Path(file), "w")
    sys.stdout = SocketConcatenator(sys.stdout, f)
    sys.stderr = SocketConcatenator(sys.stderr, f)


def reset_sockets():
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__


def get_step_from_ckpt_path(checkpoint_path: Path | str):
    if type(checkpoint_path) is str:
        checkpoint_path = Path(checkpoint_path)

    return int(checkpoint_path.stem.split("step-")[1].split(".ckpt")[0])


def get_sequence_size_from_experiment(experiment_name):
    return int(experiment_name.split("_n_")[1].split("-")[0])


def add_prefix_to_keys(dict: dict, prefix) -> dict:
    """
    Example:
        dict = {"a": 1, "b": 2}
        prefix = "text_"
        returns {"text_a": 1, "text_b": 2}
    """
    return {prefix + k: v for k, v in dict.items()}


def save_yaml(data: dict | list, path: Path):
    with open(path, mode="w", encoding="utf-8") as f:
        yaml.dump(data, f)
