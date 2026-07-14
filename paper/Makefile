PANDOC ?= pandoc
PDFLATEX ?= pdflatex
BIBTEX ?= bibtex

PANDOC_FLAGS = --from=gfm --to=latex --syntax-highlighting=none \
	--shift-heading-level-by=-1 --wrap=preserve --lua-filter=table-widths.lua

.PHONY: all arxiv-source clean

all: main.pdf catsynth-supplement.pdf

catsynth-worked-example.tex: catsynth-worked-example.md table-widths.lua
	$(PANDOC) $(PANDOC_FLAGS) $< -o $@

main.pdf: main.tex references.bib pandoc-support.tex catsynth-worked-example.tex
	$(PDFLATEX) -interaction=nonstopmode -halt-on-error main.tex
	$(BIBTEX) main
	$(PDFLATEX) -interaction=nonstopmode -halt-on-error main.tex
	$(PDFLATEX) -interaction=nonstopmode -halt-on-error main.tex

catsynth-supplement.pdf: catsynth-supplement.tex pandoc-support.tex catsynth-worked-example.tex
	$(PDFLATEX) -interaction=nonstopmode -halt-on-error catsynth-supplement.tex
	$(PDFLATEX) -interaction=nonstopmode -halt-on-error catsynth-supplement.tex

arxiv-source: catsynth-worked-example.tex
	$(PDFLATEX) -interaction=nonstopmode -halt-on-error main.tex
	$(BIBTEX) main
	$(PDFLATEX) -interaction=nonstopmode -halt-on-error main.tex
	$(PDFLATEX) -interaction=nonstopmode -halt-on-error main.tex
	sh build-arxiv-source.sh

clean:
	rm -f *.aux *.bbl *.blg *.log *.out
