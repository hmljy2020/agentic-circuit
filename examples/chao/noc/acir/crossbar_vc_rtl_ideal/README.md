# RTL-ideal 2×2 virtual-channel crossbar

This standalone example uses `ac.arbitrate greedy_fixed_priority` and
`ac.try_transfer`. The compiler lowers arbitration to direct Boolean SSA;
the capacity-1 `ac.resource` declarations are compile-time conflict tokens.

Run it with:

```sh
bash examples/chao/noc/acir/crossbar_vc_rtl_ideal/run.sh
```

The script freezes ACIR, lowers ACSim, records the ModelPlan summary, generates
and compiles C++, links the runner, and executes it twice to verify deterministic
output. Generated files stay under the ignored `build-rtl-ideal/` directory.
