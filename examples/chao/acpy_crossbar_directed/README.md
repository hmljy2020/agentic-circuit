# ACPy directed Crossbar topology

This example exercises compiler-native Crossbar specialization and directed
FlowBundle wiring.  The third instance receives exactly `a_east` as physical
input 0 and `c_north` as physical input 1.  `a_north` and `c_east` terminate at
separate queues and are not implicitly carried into `b`.

All generated artifacts should be placed in a `build-*` directory, which is
ignored here.  A useful structural check is that emitted ACIR contains three
Crossbar `ac.instance` operations, no `ac.connect`, and the `@b` operands are ordered as
the two VC leaves of `a_east` followed by the two VC leaves of `c_north`.
