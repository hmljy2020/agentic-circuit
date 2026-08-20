import argparse
from pathlib import Path


def resource(name: str) -> str:
    return f'''    ac.resource @{name} capacity 1 issue_width 1 ii 1
        latency {{kind = "fixed", ticks = 1 : i64}}
        lifecycle {{reservation = "propose_commit", release = "balanced", cancellation = "explicit"}}
        ownership "exclusive" classes [] id "{name}" path "{name}"
'''


def generate(path: Path, count: int) -> None:
    declarations = resource("shared") + "".join(
        resource(f"lane{i}") for i in range(count)
    )
    results = ", ".join(f"%g{i}" for i in range(count))
    candidates = ",\n        ".join(
        f"%request uses [@lane{i}, @shared]" for i in range(count)
    )
    types = ", ".join("i1" for _ in range(count))
    path.write_text(
        f'''builtin.module attributes {{ac.contract_epoch = "0.2"}} {{
  ac.system @scale root @Top as "root" tick 0 "cycle"
      workload @Top::@scheduler seed {{kind = "fixed", value = 0 : i64}}
      instrumentation [] results {{id = "default", format = "json"}} selected true
  ac.module @Top() parameters {{}} graph {{
{declarations}    ac.process @scheduler kind "workload" {{
      %request = arith.constant true
      {results} = ac.arbitrate greedy_fixed_priority candidates [
        {candidates}
      ] : ({types})
      ac.yield_sim
    }}
    ac.return
  }}
}}
'''
    )


def check(path: Path, count: int) -> None:
    text = path.read_text()
    assert "ac.arbitrate" not in text
    assert "arbiter" not in text.lower()
    assert "acsim.binding" not in text
    assert "invoke @acir_impl_arb" not in text
    boolean_ops = sum(text.count(f"arith.{op}") for op in ("andi", "ori", "xori"))
    # A deliberately loose, machine-independent O(E+C) ceiling.  The fixture
    # has E=2C and catches pairwise candidate comparison immediately.
    assert boolean_ops <= 6 * count, (boolean_ops, count)


parser = argparse.ArgumentParser()
parser.add_argument("mode", choices=("generate", "check"))
parser.add_argument("path", type=Path)
parser.add_argument("--count", type=int, default=256)
args = parser.parse_args()
if args.mode == "generate":
    generate(args.path, args.count)
else:
    check(args.path, args.count)
