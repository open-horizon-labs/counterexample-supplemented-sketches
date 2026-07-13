"""CatSynth: a runnable, SQLite-backed illustration of the loop from
"Agentic Synthesis against Counterexample-Supplemented Sketches".

The domain is deliberately small: recommend a cat breed for an owner profile.
Cat facts come from Wikipedia (cached into SQLite). Local tables hold the
owner-trait rulesets. An evolved sketch carries learned policy. The SQLite
table projects operator-approved counterexamples into both archive A and
regression set R; this small demo uses A = R. A two-layer gate (replay +
semantic compare) checks the current resolver against R.
"""

__all__ = ["DB_PATH"]

import os

DB_PATH = os.environ.get(
    "CATSYNTH_DB",
    os.path.join(os.path.dirname(__file__), "..", "catsynth.db"),
)
