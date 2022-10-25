import contextlib
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set

import zkvvm
from ape.api import CompilerAPI
from semantic_version import SimpleSpec, Version


class ZKVyperCompiler(CompilerAPI):
    @property
    def name(self) -> str:
        return "zkVyper"

    def get_versions(self, all_paths: List[Path]) -> Set[str]:
        pattern = re.compile(r"\s* # \s+ @zk-version \s+ (.+)", re.VERBOSE)
        versions = []
        with contextlib.ExitStack() as stack:
            files = [stack.enter_context(fp.open()) for fp in all_paths]
            for file in files:
                mo = pattern.match(file.readline())
                with contextlib.suppress(ValueError):
                    versions.append(str(SimpleSpec(mo.group(1) if mo else "latest")))
        return set(versions)

    def get_version_map(
        self, contract_filepaths: List[Path], base_path: Optional[Path] = None
    ) -> Dict[Version, Set[Path]]:
        version_specs = [SimpleSpec(v) for v in self.get_versions(contract_filepaths)]
        version_manager = zkvvm.VersionManager(zkvvm.Config())
        for spec in version_specs:
            if spec.select(version_manager.local_versions):
                continue
            selected = spec.select(version_manager.remote_versions)
            if not selected:
                raise ValueError(f"No zkVyper version meeting constraint: {spec!s}")
            version_manager.install(selected, show_progress=True)

        pattern = re.compile(r"\s* # \s+ @zk-version \s+ (.+)", re.VERBOSE)
        version_map = defaultdict(set)
        with contextlib.ExitStack() as stack:
            for fp in contract_filepaths:
                mo = pattern.match(stack.enter_context(fp.open()).readline())
                try:
                    spec = SimpleSpec(mo.group(1) if mo else ">=0.1.0")
                except ValueError:
                    spec = SimpleSpec(">=0.1.0")
                version = spec.select(version_manager.local_versions)
                version_map[version].add(fp)
        return version_map
