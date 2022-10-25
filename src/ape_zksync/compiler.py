from ape.api import CompilerAPI


class ZKVyperCompiler(CompilerAPI):
    @property
    def name(self) -> str:
        return "zkVyper"
