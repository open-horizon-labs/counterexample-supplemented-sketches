"""CatSynth: a runnable, SQLite-backed illustration of the loop from
"Agentic Synthesis against Counterexample-Supplemented Sketches".

The domain is deliberately small: recommend a cat breed for an owner profile.
Cat facts come from Wikipedia (cached into SQLite). Local tables hold the
owner-trait rulesets. A sketch fixes the strategy, a golden corpus stores
promoted counterexamples, and a two-layer gate (replay + semantic compare)
checks that the current resolver satisfies every promoted case.
"""

__all__ = ["DB_PATH"]

import os

DB_PATH = os.environ.get(
    "CATSYNTH_DB",
    os.path.join(os.path.dirname(__file__), "..", "catsynth.db"),
)
