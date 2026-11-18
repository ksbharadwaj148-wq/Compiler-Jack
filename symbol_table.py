class SymbolTable:
    """Stores class-level and subroutine-level Jack identifiers."""

    def __init__(self):
        self.class_symbols = {}
        self.subroutine_symbols = {}
        self.counts = {"STATIC": 0, "FIELD": 0, "ARG": 0, "VAR": 0}

    def start_subroutine(self):
        self.subroutine_symbols = {}
        self.counts["ARG"] = 0
        self.counts["VAR"] = 0

    def define(self, name, type_, kind):
        kind = kind.upper()
        if kind not in self.counts:
            raise ValueError(f"Unknown symbol kind: {kind}")
        table = self.class_symbols if kind in ("STATIC", "FIELD") else self.subroutine_symbols
        table[name] = {"type": type_, "kind": kind, "index": self.counts[kind]}
        self.counts[kind] += 1

    def var_count(self, kind):
        return self.counts[kind.upper()]

    def _lookup(self, name):
        # Local/argument symbols shadow class-level symbols.
        if name in self.subroutine_symbols:
            return self.subroutine_symbols[name]
        return self.class_symbols.get(name)

    def kind_of(self, name):
        item = self._lookup(name)
        return item["kind"] if item else None

    def type_of(self, name):
        item = self._lookup(name)
        return item["type"] if item else None

    def index_of(self, name):
        item = self._lookup(name)
        return item["index"] if item else None
