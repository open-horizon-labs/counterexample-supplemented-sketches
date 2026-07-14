# Paper builds and arXiv packaging

`main.pdf` is the canonical distributed paper. It includes the CatSynth artifact supplement as
an appendix after the references. `catsynth-supplement.pdf` renders the same supplement body as a
standalone convenience artifact.

Build both PDFs from this directory:

```bash
make
```

The Markdown file `catsynth-worked-example.md` is the editable supplement source. Pandoc generates
`catsynth-worked-example.tex`; both PDFs include that generated fragment. Commit the generated TeX
whenever the Markdown changes so arXiv can compile the paper without running Pandoc.

## arXiv source package

Submit the PDFLaTeX source for the combined paper, not two independently compiled PDFs. Include:

- `main.tex`;
- `main.bbl` or `references.bib`;
- `pandoc-support.tex`;
- `catsynth-worked-example.tex`;
- the image files under `figures/` that `main.tex` and the supplement reference.

Do not include `catsynth-supplement.tex`, either generated PDF, or LaTeX build intermediates in
the arXiv source package. The standalone supplement belongs in the repository or release assets.
The repository already carries the full experiment traces, so the arXiv submission does not need
to duplicate them as ancillary files.
