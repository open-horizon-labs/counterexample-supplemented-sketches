"""CatSynth command-line entry point.

Examples:
    python cli.py seed                 # seed DB + fetch Wikipedia facts (cached)
    python cli.py seed --no-wiki       # seed DB without any network
    python cli.py gate                 # run the gate in policy mode
    python cli.py gate --mode naive    # run the gate with the tempting resolver
    python cli.py suggest allergy_lapcat
    python cli.py serve                # launch the local web UI
"""

from __future__ import annotations

import argparse
import json

from catsynth import db, resolver, seed
from catsynth.gate import run_gate


def cmd_seed(args):
    conn = db.connect()
    seed.seed_all(conn, fetch_wiki_facts=not args.no_wiki, refresh_wiki=args.refresh_wiki)
    conn.close()


def cmd_gate(args):
    conn = db.connect()
    summary = run_gate(conn, mode=args.mode)
    conn.close()
    print(f"\nGate ({summary['mode']} mode): "
          f"{'PASS' if summary['passed'] else 'FAIL'} "
          f"[{summary['passed_count']}/{summary['total']}]\n")
    for c in summary["cases"]:
        mark = "PASS" if c["passed"] else "FAIL"
        print(f"  [{mark}] {c['scenario_id']} ({c['sketch_clause']})")
        print(f"        replay : {'ok ' if c['replay']['passed'] else 'FAIL'} - {c['replay']['detail']}")
        cf = c["compare"]["fields"]
        comp = "ok " if c["compare"]["passed"] else "FAIL"
        print(f"        compare: {comp} - operation={cf['operation']['actual']} "
              f"breed={cf['breed']['actual']} (expected breed={cf['breed']['expected']})")
        print(f"        -> {c['interpretation']}")
    raise SystemExit(0 if summary["passed"] else 1)


def cmd_suggest(args):
    conn = db.connect()
    owner = db.get_scenario(conn, args.scenario_id)
    if owner is None:
        raise SystemExit(f"unknown scenario {args.scenario_id!r}")
    rec = resolver.resolve(conn, owner, mode=args.mode)
    conn.close()
    print(json.dumps({"scenario": owner.to_dict(), "recommendation": rec.to_dict()}, indent=2))


def cmd_serve(args):
    import uvicorn
    uvicorn.run("catsynth.app:app", host=args.host, port=args.port, reload=args.reload)


def main():
    p = argparse.ArgumentParser(description="CatSynth: agentic synthesis loop demo")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("seed", help="seed the database")
    ps.add_argument("--no-wiki", action="store_true", help="skip Wikipedia fetch")
    ps.add_argument("--refresh-wiki", action="store_true", help="re-fetch cached facts")
    ps.set_defaults(func=cmd_seed)

    pg = sub.add_parser("gate", help="run the gate over the regression set")
    pg.add_argument("--mode", choices=["policy", "naive"], default="policy")
    pg.set_defaults(func=cmd_gate)

    pu = sub.add_parser("suggest", help="run the resolver on one scenario")
    pu.add_argument("scenario_id")
    pu.add_argument("--mode", choices=["policy", "naive"], default="policy")
    pu.set_defaults(func=cmd_suggest)

    pv = sub.add_parser("serve", help="launch the local web UI")
    pv.add_argument("--host", default="127.0.0.1")
    pv.add_argument("--port", type=int, default=8000)
    pv.add_argument("--reload", action="store_true")
    pv.set_defaults(func=cmd_serve)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
