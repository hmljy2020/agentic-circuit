"""Closed ACPy record declarations and deterministic natural layout."""

from __future__ import annotations

import ast
from dataclasses import dataclass

from ._definitions import Definition
from ._frontend import CapturedProgram
from ._source import DefinitionSite


_SCALARS: dict[str, tuple[str, int, int]] = {
    "i8": ("i8", 1, 1),
    "i16": ("i16", 2, 2),
    "i32": ("i32", 4, 4),
    "i64": ("i64", 8, 8),
    "f32": ("f32", 4, 4),
    "f64": ("f64", 8, 8),
}


@dataclass(frozen=True, slots=True)
class RecordField:
    name: str
    type_key: str
    acir_type: str
    offset: int


@dataclass(frozen=True, slots=True)
class RecordDefinition:
    name: str
    kind: str
    endianness: str
    fields: tuple[RecordField, ...]
    size: int
    alignment: int
    site: DefinitionSite

    @property
    def acir_type(self) -> str:
        return f"!ac.{self.kind}<@types::@{self.name}>"


def _annotation_key(node: ast.expr) -> str:
    return ast.unparse(node)


def _vector(node: ast.expr) -> tuple[ast.expr, int] | None:
    if not (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == "Vector"
    ):
        return None
    elements = node.slice.elts if isinstance(node.slice, ast.Tuple) else []
    if (
        len(elements) != 2
        or not isinstance(elements[1], ast.Constant)
        or type(elements[1].value) is not int
        or elements[1].value <= 0
    ):
        raise ValueError("ACPY-TYPE-PACKET: Vector requires one type and a positive static length")
    return elements[0], elements[1].value


def _round_up(value: int, alignment: int) -> int:
    return value + (-value % alignment)


def collect_record_definitions(captured: CapturedProgram) -> tuple[RecordDefinition, ...]:
    definitions = {
        definition.qualified_name: definition
        for definition in captured.definitions
        if definition.kind in {"struct", "packet"}
    }
    sites = {site.qualified_name: site for site in captured.source.definitions}
    raw: dict[str, tuple[Definition, DefinitionSite, tuple[tuple[str, ast.expr], ...], str]] = {}
    for qualified_name, definition in definitions.items():
        site = sites[qualified_name]
        node = site.node
        if not isinstance(node, ast.FunctionDef):
            raise ValueError("ACPY-TYPE-PACKET: record declarations must decorate functions")
        options = dict(definition.explicit_options)
        if set(options) - {"endianness"}:
            raise ValueError(f"ACPY-TYPE-PACKET: {definition.__name__} has unsupported options")
        endianness = options.get("endianness", "little")
        if endianness not in {"little", "big"}:
            raise ValueError("ACPY-TYPE-PACKET: endianness must be 'little' or 'big'")
        arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        if not arguments:
            raise ValueError(f"ACPY-TYPE-PACKET: {definition.__name__} must declare fields")
        if node.args.vararg is not None or node.args.kwarg is not None:
            raise ValueError("ACPY-TYPE-PACKET: record fields cannot be variadic")
        if node.args.defaults or any(item is not None for item in node.args.kw_defaults):
            raise ValueError("ACPY-TYPE-PACKET: record fields cannot have defaults")
        if any(argument.annotation is None for argument in arguments):
            raise ValueError("ACPY-TYPE-PACKET: every record field requires a type")
        if any(
            not isinstance(statement, ast.Pass)
            and not (
                isinstance(statement, ast.Return)
                and (statement.value is None or isinstance(statement.value, ast.Constant) and statement.value.value is None)
            )
            for statement in node.body
        ):
            raise ValueError("ACPY-TYPE-PACKET: record declaration body must be empty")
        fields = tuple((argument.arg, argument.annotation) for argument in arguments if argument.annotation is not None)
        raw[definition.__name__] = (definition, site, fields, endianness)

    resolved: dict[str, RecordDefinition] = {}
    resolving: set[str] = set()

    def type_layout(node: ast.expr) -> tuple[str, int, int]:
        if isinstance(node, ast.Name) and node.id in _SCALARS:
            return _SCALARS[node.id]
        vector = _vector(node)
        if vector is not None:
            element, length = vector
            element_type, size, alignment = type_layout(element)
            return f"!ac.vector<{length} x {element_type}>", size * length, alignment
        if isinstance(node, ast.Name) and node.id in raw:
            nested = resolve(node.id)
            return nested.acir_type, nested.size, nested.alignment
        raise ValueError(f"ACPY-TYPE-PACKET: unsupported record field type {_annotation_key(node)!r}")

    def resolve(name: str) -> RecordDefinition:
        if name in resolved:
            return resolved[name]
        if name in resolving:
            raise ValueError(f"ACPY-TYPE-PACKET: recursive record definition {name!r}")
        resolving.add(name)
        definition, site, field_nodes, endianness = raw[name]
        cursor = 0
        alignment = 1
        fields: list[RecordField] = []
        for field_name, annotation in field_nodes:
            acir_type, size, field_alignment = type_layout(annotation)
            cursor = _round_up(cursor, field_alignment)
            fields.append(RecordField(field_name, _annotation_key(annotation), acir_type, cursor))
            cursor += size
            alignment = max(alignment, field_alignment)
        size = _round_up(cursor, alignment)
        record = RecordDefinition(
            definition.__name__, definition.kind, endianness, tuple(fields), size, alignment, site
        )
        resolving.remove(name)
        resolved[name] = record
        return record

    for name in raw:
        resolve(name)
    return tuple(resolved[name] for name in sorted(resolved))


def named_acir_type(name: str, records: tuple[RecordDefinition, ...]) -> str | None:
    record = next((record for record in records if record.name == name), None)
    return record.acir_type if record is not None else None


def record_by_name(name: str, records: tuple[RecordDefinition, ...]) -> RecordDefinition | None:
    return next((record for record in records if record.name == name), None)
