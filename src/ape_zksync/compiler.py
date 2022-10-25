import contextlib
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set

import zkvvm
from ape.api import CompilerAPI
from ethpm_types import ContractType
from semantic_version import SimpleSpec, Version

PATTERN = re.compile(r"\s* \# \s+ @zk-version \s+ (.+)", re.VERBOSE)


class ZKVyperCompiler(CompilerAPI):
    @property
    def name(self) -> str:
        return "zkVyper"

    def get_versions(self, all_paths: List[Path]) -> Set[str]:
        versions = []
        with contextlib.ExitStack() as stack:
            files = [stack.enter_context(fp.open()) for fp in all_paths]
            for file in files:
                mo = PATTERN.match(file.readline())
                with contextlib.suppress(ValueError):
                    versions.append(str(SimpleSpec(mo.group(1) if mo else "latest")))
        return set(versions)

    def get_compiler_settings(
        self, contract_filepaths: List[Path], base_path: Optional[Path] = None
    ) -> Dict[Version, Dict]:
        return {
            ver: {}
            for ver in self.get_version_map(contract_filepaths, base_path).keys()
        }

    def compile(
        self, contract_filepaths: List[Path], base_path: Optional[Path]
    ) -> List[ContractType]:
        config = zkvvm.Config()
        version_manager = zkvvm.VersionManager(config)

        base_path = base_path or self.config_manager.contracts_folder
        version_map = self.get_version_map(
            [p for p in contract_filepaths if p.parent.name != "interfaces"]
        )

        contracts = []
        for zk_version, source_paths in version_map.items():
            config["zk_version"] = SimpleSpec(str(zk_version))
            output = version_manager.compile(source_paths)
            for fp, o in output.items():
                if not isinstance(o, dict):
                    continue
                o["contractName"] = Path(fp).stem
                o["sourceId"] = fp
                o["deploymentBytecode"] = {"bytecode": o["bytecode"]}
                o["runtimeBytecode"] = {"bytecode": o["bytecode_runtime"]}
                o["zk_version"] = str(zk_version)
                o["vyper_version"] = str(config["vyper_version"])
                contracts.append(ContractType.parse_obj(o))
        return contracts

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

        version_map = defaultdict(set)
        with contextlib.ExitStack() as stack:
            for fp in contract_filepaths:
                mo = PATTERN.match(stack.enter_context(fp.open()).readline())
                try:
                    spec = SimpleSpec(mo.group(1) if mo else ">=0.1.0")
                except ValueError:
                    spec = SimpleSpec(">=0.1.0")
                version = spec.select(version_manager.local_versions)
                version_map[version].add(fp)
        return version_map
