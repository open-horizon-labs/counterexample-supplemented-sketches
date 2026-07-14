# Task-line parser: compact end-state example

This example shows the durable end state of the method:

- [`sketch.md`](sketch.md) is the evolved synthesis of the accepted counterexamples.
- [`counterexamples.md`](counterexamples.md) is the complete archive explaining why the sketch
  changed.
- [`tests/`](tests/) is the executable regression corpus.
- [`generated/`](generated/) is replaceable code that should be regenerable from the sketch and
  known-code anchors.

The example is small, so every archived CE remains in the regression corpus. Larger systems can
select a smaller discriminating subset as long as it still rejects the known tempting repairs.

This directory shows the durable end state, not the live review UI. In the full method, each
case entered the archive only after an operator explicitly approved it as a counterexample to
the current sketch and made the corrected behavior authoritative.

The key test is clean regeneration: delete or ignore the generated parser, implement the evolved
sketch without reading the CE archive as prompt context, and run the regression corpus.
