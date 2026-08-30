"""Kalkulator yang aman dipanggil model — contoh guardrail modul A4.

Sengaja TIDAK memakai eval(). eval() akan menjalankan kode Python apa pun —
termasuk yang berbahaya bila ekspresinya datang dari sumber tak tepercaya, dan
teks yang ditulis model ADALAH sumber tak tepercaya. Di sini hanya operator
aritmetika yang di-whitelist: batasi kemampuan alat sampai sebatas yang
benar-benar diperlukan.
"""
from __future__ import annotations

import ast
import operator
from collections.abc import Callable

from ..errors import UnsafeExpression

OPERATOR: dict[type[ast.AST], Callable] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

REJECTED_MESSAGE = "hanya angka dan operator + - * / % ** yang diizinkan"


def _score(simpul: ast.AST) -> float:
    if isinstance(simpul, ast.Constant) and isinstance(simpul.value, (int, float)):
        return simpul.value
    if isinstance(simpul, ast.BinOp) and type(simpul.op) in OPERATOR:
        return OPERATOR[type(simpul.op)](_score(simpul.left), _score(simpul.right))
    if isinstance(simpul, ast.UnaryOp) and type(simpul.op) in OPERATOR:
        return OPERATOR[type(simpul.op)](_score(simpul.operand))
    raise UnsafeExpression(REJECTED_MESSAGE)


def eval_expression(expression: str) -> float:
    """Hitung ekspresi aritmetika sederhana.

    Melempar `EkspresiTidakAman` untuk apa pun di luar angka dan operator
    yang diizinkan — termasuk nama variabel, pemanggilan fungsi, dan atribut.
    """
    try:
        pohon = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise UnsafeExpression(f"bukan ekspresi yang sah: {expression!r}") from e
    return _score(pohon.body)
