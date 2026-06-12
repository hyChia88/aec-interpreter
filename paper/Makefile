# Build the thesis PDF. Toolchain: pdflatex + bibtex (no latexmk/tectonic on this host).
MAIN = main

all: $(MAIN).pdf

$(MAIN).pdf: $(MAIN).tex sections/*.tex references.bib
	pdflatex -interaction=nonstopmode -halt-on-error $(MAIN)
	bibtex $(MAIN)
	pdflatex -interaction=nonstopmode -halt-on-error $(MAIN)
	pdflatex -interaction=nonstopmode -halt-on-error $(MAIN)

clean:
	rm -f $(MAIN).aux $(MAIN).bbl $(MAIN).blg $(MAIN).log $(MAIN).out $(MAIN).toc

cleanall: clean
	rm -f $(MAIN).pdf

.PHONY: all clean cleanall
