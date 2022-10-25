import contextlib
import re
from pathlib import Path
from typing import List, Set

from ape.api import CompilerAPI
from semantic_version import NpmSpec


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
                    versions.append(str(NpmSpec(mo.group(1) if mo else "latest")))
        return set(versions)
