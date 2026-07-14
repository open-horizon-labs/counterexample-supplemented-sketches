#!/bin/sh
set -eu

paper_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
dist_dir="$paper_dir/../dist"
source_dir="$dist_dir/arxiv-source"
check_dir="$dist_dir/arxiv-check"
archive="$dist_dir/agentic-synthesis-arxiv-source.zip"

cd "$paper_dir"

rm -rf "$source_dir" "$check_dir"
rm -f "$archive"
mkdir -p "$source_dir/figures/catsynth" "$check_dir"

cp main.tex main.bbl pandoc-support.tex catsynth-worked-example.tex "$source_dir/"
cp figures/catsynth/01-method-overview.png "$source_dir/figures/catsynth/"
cp figures/catsynth/02-tempting-result.png "$source_dir/figures/catsynth/"
cp figures/catsynth/03-promoted-corpus.png "$source_dir/figures/catsynth/"
cp figures/catsynth/04-naive-gate.png "$source_dir/figures/catsynth/"

(
  cd "$source_dir"
  zip -X -q "$archive" \
    main.tex \
    main.bbl \
    pandoc-support.tex \
    catsynth-worked-example.tex \
    figures/catsynth/01-method-overview.png \
    figures/catsynth/02-tempting-result.png \
    figures/catsynth/03-promoted-corpus.png \
    figures/catsynth/04-naive-gate.png
)

unzip -t "$archive"
unzip -q "$archive" -d "$check_dir"

(
  cd "$check_dir"
  pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null
  pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null
  pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null

  if grep -Eq 'Citation .* undefined|Reference .* undefined|There were undefined references|Overfull \\[hv]box' main.log; then
    echo "arXiv package compiled with unresolved citations, references, or overfull boxes" >&2
    exit 1
  fi
)

printf '%s\n' "$archive"
