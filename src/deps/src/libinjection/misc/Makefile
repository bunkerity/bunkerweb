
all:site

PAGES = \
	home.html
%.html: %.md base.html
	echo $<
	./mdgen.sh $< > $@

clean:
	rm -f ${PAGES}

site: Makefile ${PAGES}

.PHONY: site
