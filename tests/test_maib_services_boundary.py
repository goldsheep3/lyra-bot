from __future__ import annotations

import ast
import unittest
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIB_ROOT = ROOT / "plugins" / "maib"


# These APIs only exchange scalars, utils objects, or explicit public result
# objects.  Their implementation may use ORM models internally.
PURE_SERVICE_APIS = {
    "add_aime",
    "add_ma",
    "add_ma_batch",
    "add_record_batch",
    "authenticate_access_token",
    "backfill_record_shortids",
    "create_pairing_code",
    "del_mu_tgid",
    "exchange_pairing_code",
    "get_last_sy_hash",
    "get_pending_mappings",
    "get_record_achs",
    "resolve_id_mapping",
    "rfs_dxra_batch",
    "set_last_sy_hash",
    "set_mct_level_batch",
    "set_mdt_version_batch",
    "set_mu_tgid",
    "set_mu_username",
    "unlink_aime",
    "upd_ach_batch",
    "upd_mdt_tg_fileid",
}


# These currently return or accept services ORM entities.  Calls remain in the
# baseline while the services boundary is being refactored.
ORM_SERVICE_APIS = {
    "check_mu",
    "get_aime",
    "get_aime_with_access4",
    "get_b50",
    "get_ma",
    "get_mca_list",
    "get_mct_list",
    "get_mdt",
    "get_mdt_list",
    "get_mu",
    "get_mu_from_tgid",
    "get_user_aimes",
    "set_mct_level",
    "sync_mdt_list",
}


ORM_SERVICE_SYMBOLS = {
    "MaiAlias",
    "MaiChart",
    "MaiChartAch",
    "MaiData",
    "MaiIDMap",
    "MaiLxns",
    "MaiRecord",
    "MaiSync",
    "MaiUser",
    "Maime",
}


INTERNAL_SERVICE_APIS = {"execute_func", "get_session"}


# Public exceptions and explicit result objects are valid boundary types.
PUBLIC_SERVICE_TYPES = {
    "AccessTokenError",
    "PairingCodeError",
    "PairingCodeIssueResult",
}


@dataclass(frozen=True, slots=True)
class ServiceCall:
    path: str
    line: int
    symbol: str
    passes_session: bool

    @property
    def root(self) -> str:
        return self.symbol.split(".", 1)[0]


@dataclass(frozen=True, slots=True)
class BoundaryViolation:
    path: str
    line: int
    symbol: str
    reason: str

    @property
    def baseline_key(self) -> tuple[str, str, str]:
        return self.path, self.symbol, self.reason


def _attribute_chain(node: ast.AST) -> list[str] | None:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return list(reversed(parts))


class _ServicesUsageScanner(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.services_aliases: set[str] = set()
        self.direct_imports: dict[str, str] = {}
        self.model_imports: list[BoundaryViolation] = []
        self.calls: list[ServiceCall] = []
        self.orm_references: set[tuple[int, str]] = set()

    def visit_Import(self, node: ast.Import) -> None:
        for name in node.names:
            if name.name.endswith(".services"):
                self.services_aliases.add(name.asname or name.name.rsplit(".", 1)[-1])
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        if module.endswith("services.models"):
            for name in node.names:
                bound_name = name.asname or name.name
                self.model_imports.append(
                    BoundaryViolation(
                        path=self._relative_path,
                        line=node.lineno,
                        symbol=name.name,
                        reason="imports_services_orm",
                    )
                )
                self.direct_imports[bound_name] = name.name
        elif module.endswith("services"):
            for name in node.names:
                bound_name = name.asname or name.name
                self.direct_imports[bound_name] = name.name
                if name.name in ORM_SERVICE_SYMBOLS:
                    self.model_imports.append(
                        BoundaryViolation(
                            path=self._relative_path,
                            line=node.lineno,
                            symbol=name.name,
                            reason="imports_services_orm",
                        )
                    )
                elif name.name in INTERNAL_SERVICE_APIS:
                    self.model_imports.append(
                        BoundaryViolation(
                            path=self._relative_path,
                            line=node.lineno,
                            symbol=name.name,
                            reason="imports_internal_service_api",
                        )
                    )
        else:
            for name in node.names:
                if name.name == "services":
                    self.services_aliases.add(name.asname or name.name)
        self.generic_visit(node)

    @property
    def _relative_path(self) -> str:
        return self.path.relative_to(ROOT).as_posix()

    def _resolve_service_symbol(self, node: ast.AST) -> str | None:
        chain = _attribute_chain(node)
        if not chain:
            return None
        if chain[0] in self.services_aliases and len(chain) > 1:
            return ".".join(chain[1:])
        direct = self.direct_imports.get(chain[0])
        if direct is not None:
            return ".".join([direct, *chain[1:]])
        return None

    def visit_Call(self, node: ast.Call) -> None:
        symbol = self._resolve_service_symbol(node.func)
        if symbol is not None:
            self.calls.append(
                ServiceCall(
                    path=self._relative_path,
                    line=node.lineno,
                    symbol=symbol,
                    passes_session=any(keyword.arg == "session" for keyword in node.keywords),
                )
            )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        symbol = self._resolve_service_symbol(node)
        if symbol is not None:
            root = symbol.split(".", 1)[0]
            if root in ORM_SERVICE_SYMBOLS:
                # Report the exported ORM symbol once per source line.  A
                # chain such as services.MaiData.from_utils otherwise visits
                # both MaiData and MaiData.from_utils as separate attributes.
                self.orm_references.add((node.lineno, root))
        self.generic_visit(node)


def scan_external_services_usage() -> tuple[list[ServiceCall], list[BoundaryViolation]]:
    calls: list[ServiceCall] = []
    violations: list[BoundaryViolation] = []

    for path in sorted(MAIB_ROOT.rglob("*.py")):
        relative = path.relative_to(MAIB_ROOT)
        if relative.parts[0] in {"services", "migrations"}:
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        scanner = _ServicesUsageScanner(path)
        scanner.visit(tree)
        calls.extend(scanner.calls)
        violations.extend(scanner.model_imports)

        for line, symbol in sorted(scanner.orm_references):
            violations.append(
                BoundaryViolation(
                    path=path.relative_to(ROOT).as_posix(),
                    line=line,
                    symbol=symbol,
                    reason="references_services_orm",
                )
            )

    for call in calls:
        if call.root in ORM_SERVICE_APIS:
            violations.append(
                BoundaryViolation(
                    path=call.path,
                    line=call.line,
                    symbol=call.symbol,
                    reason="calls_orm_service_api",
                )
            )
        elif call.root in INTERNAL_SERVICE_APIS:
            violations.append(
                BoundaryViolation(
                    path=call.path,
                    line=call.line,
                    symbol=call.symbol,
                    reason="calls_internal_service_api",
                )
            )
        elif call.root in ORM_SERVICE_SYMBOLS:
            # The attribute visitor already records the ORM reference.  Keep
            # calls classified here without duplicating the violation.
            continue
        elif call.root in PURE_SERVICE_APIS:
            if call.passes_session:
                violations.append(
                    BoundaryViolation(
                        path=call.path,
                        line=call.line,
                        symbol=call.symbol,
                        reason="passes_session_across_boundary",
                    )
                )
        elif call.root not in PUBLIC_SERVICE_TYPES:
            violations.append(
                BoundaryViolation(
                    path=call.path,
                    line=call.line,
                    symbol=call.symbol,
                    reason="unclassified_service_api",
                )
            )

    return calls, violations


# Ratchet baseline: known debt is allowed to disappear, but no file may add
# another occurrence without explicitly updating this inventory.  Counts make
# repeated calls in the same file visible as new boundary debt.
KNOWN_IMPURE_USAGE_MAXIMUMS: Counter[tuple[str, str, str]] = Counter(
    {
        ("plugins/maib/fetch.py", "MaiData", "references_services_orm"): 2,
        ("plugins/maib/fetch.py", "get_session", "calls_internal_service_api"): 2,
        ("plugins/maib/fetch.py", "rfs_dxra_batch", "passes_session_across_boundary"): 1,
        ("plugins/maib/fetch.py", "set_mct_level_batch", "passes_session_across_boundary"): 1,
        ("plugins/maib/fetch.py", "set_mdt_version_batch", "passes_session_across_boundary"): 1,
        ("plugins/maib/fetch.py", "sync_mdt_list", "calls_orm_service_api"): 1,
        ("plugins/maib/matcher/adx_download.py", "MaiData", "references_services_orm"): 1,
        ("plugins/maib/matcher/adx_download.py", "get_mdt.id", "calls_orm_service_api"): 1,
        ("plugins/maib/matcher/alias.py", "MaiData", "references_services_orm"): 1,
        ("plugins/maib/matcher/alias.py", "get_mdt.id", "calls_orm_service_api"): 1,
        ("plugins/maib/matcher/context.py", "check_mu", "calls_orm_service_api"): 1,
        ("plugins/maib/matcher/context.py", "get_mdt.id", "calls_orm_service_api"): 1,
        ("plugins/maib/matcher/context.py", "get_mu_from_tgid", "calls_orm_service_api"): 1,
        ("plugins/maib/matcher/dxrating_calc.py", "get_mdt.id", "calls_orm_service_api"): 1,
        ("plugins/maib/matcher/info.py", "MaiData", "references_services_orm"): 1,
        ("plugins/maib/matcher/info.py", "check_mu", "calls_orm_service_api"): 1,
        ("plugins/maib/matcher/info.py", "get_mdt.id", "calls_orm_service_api"): 1,
        ("plugins/maib/matcher/info.py", "get_mdt.title", "calls_orm_service_api"): 1,
        ("plugins/maib/matcher/info.py", "get_mu_from_tgid", "calls_orm_service_api"): 1,
        ("plugins/maib/matcher/info_list.py", "MaiChartAch", "references_services_orm"): 1,
        ("plugins/maib/matcher/info_list.py", "check_mu", "calls_orm_service_api"): 1,
        ("plugins/maib/matcher/info_list.py", "get_b50", "calls_orm_service_api"): 1,
        ("plugins/maib/matcher/info_list.py", "get_mct_list.level", "calls_orm_service_api"): 2,
        ("plugins/maib/matcher/info_list.py", "get_mu_from_tgid", "calls_orm_service_api"): 1,
        ("plugins/maib/matcher/maime.py", "get_aime", "calls_orm_service_api"): 3,
        ("plugins/maib/matcher/maime.py", "get_aime_with_access4", "calls_orm_service_api"): 1,
        ("plugins/maib/matcher/maime.py", "get_user_aimes", "calls_orm_service_api"): 1,
        ("plugins/maib/matcher/sync.py", "MaiUser", "imports_services_orm"): 1,
        ("plugins/maib/matcher/sync.py", "check_mu", "calls_orm_service_api"): 2,
        ("plugins/maib/matcher/sync.py", "get_mdt.title", "calls_orm_service_api"): 1,
        ("plugins/maib/matcher/temp_link.py", "check_mu", "calls_orm_service_api"): 1,
        ("plugins/maib/matcher/temp_link.py", "get_mu_from_tgid", "calls_orm_service_api"): 1,
        ("plugins/maib/mcp/__init__.py", "MaiData", "references_services_orm"): 1,
        ("plugins/maib/mcp/__init__.py", "get_mdt.id", "calls_orm_service_api"): 1,
        ("plugins/maib/mcp/__init__.py", "get_mdt.title", "calls_orm_service_api"): 1,
        ("plugins/maib/mcp/__init__.py", "get_session", "calls_internal_service_api"): 1,
    }
)


class MaibServicesBoundaryTest(unittest.TestCase):
    def test_every_external_services_call_is_classified(self) -> None:
        calls, _ = scan_external_services_usage()
        unclassified = [
            call
            for call in calls
            if call.root
            not in (
                PURE_SERVICE_APIS
                | ORM_SERVICE_APIS
                | ORM_SERVICE_SYMBOLS
                | INTERNAL_SERVICE_APIS
                | PUBLIC_SERVICE_TYPES
            )
        ]
        self.assertEqual(
            unclassified,
            [],
            "Unclassified external services calls:\n"
            + "\n".join(
                f"{call.path}:{call.line}: {call.symbol}" for call in unclassified
            ),
        )

    def test_no_new_impure_external_services_usage(self) -> None:
        _, violations = scan_external_services_usage()
        actual = Counter(violation.baseline_key for violation in violations)
        excess = actual - KNOWN_IMPURE_USAGE_MAXIMUMS
        self.assertEqual(
            excess,
            Counter(),
            "External services boundary violations exceeded the migration baseline:\n"
            + "\n".join(
                f"{count}x {path}: {symbol} [{reason}]"
                for (path, symbol, reason), count in sorted(excess.items())
            ),
        )


if __name__ == "__main__":
    unittest.main()
