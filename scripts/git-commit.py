#!/usr/bin/env python3

import json
import shutil
import subprocess
from argparse import ArgumentParser
from datetime import datetime, UTC
from pathlib import Path

MODULES_JSON = "modules.json"
JSON_DIR = "json"
MODULES_DIR = "modules"
GITHUB_MAX_SIZE = 50 * 1024 * 1024


class Git:
    def __init__(self, working_dir: Path):
        self._cwd_dir = working_dir
        self._json_dir = working_dir.joinpath(JSON_DIR)
        self._modules_dir = working_dir.joinpath(MODULES_DIR)

        self._modules_json = self._json_dir.joinpath(MODULES_JSON)

    def remove(self):
        for module_dir in sorted(self._modules_dir.glob("[!.]*/")):
            if self.skip_it(module_dir):
                print(f"remove: {module_dir.name}")
                shutil.rmtree(module_dir, ignore_errors=True)

    def upgrade(self):
        subprocess.run(
            args=["mrepo", "upgrade", "--pretty"],
            check=True,
            cwd=self._cwd_dir
        )

    def add(self):
        subprocess.run(
            args=["git", "add", '--all'],
            check=True,
            cwd=self._cwd_dir
        )

    def commit(self):
        with open(self._modules_json, "r") as f:
            modules = json.load(f)

        timestamp = modules["timestamp"] / 1000
        time = datetime.fromtimestamp(timestamp, UTC)
        msg = f"Update by CLI ({time})"

        subprocess.run(
            args=["git", "commit", "-m", msg],
            check=True,
            cwd=self._cwd_dir
        )

    @classmethod
    def skip_it(cls, module_dir: Path) -> bool:
        for file in module_dir.glob("*.zip"):
            if file.stat().st_size >= GITHUB_MAX_SIZE:
                return True

        return False


class Main:
    @classmethod
    def generate_parser(cls) -> ArgumentParser:
        cwd_folder = Path(__name__).resolve().parent
        print(cwd_folder)

        parser = ArgumentParser()
        parser.add_argument(
            "-D",
            "--directory",
            dest="working_dir",
            metavar="DIR",
            type=str,
            default=cwd_folder.as_posix(),
            help="set working directory"
        )

        return parser

    @classmethod
    def exec(cls):
        parser = cls.generate_parser()
        args = parser.parse_args()
        working_dir = Path(args.working_dir)

        git = Git(working_dir)
        git.remove()
        git.upgrade()
        git.add()
        git.commit()


if __name__ == "__main__":
    Main.exec()
