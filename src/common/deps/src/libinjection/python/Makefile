
all: build
#
#

build: copy libinjection/libinjection_wrap.c
	rm -f libinjection.py libinjection.pyc
	python setup.py --verbose build --force

install: build
	sudo python setup.py --verbose install

test-unit: build words.py
	python setup.py build_ext --inplace
	PYTHON_PATH='.' nosetests -v --with-xunit test_driver.py

.PHONY: test
test: test-unit

.PHONY: speed
speed:
	./speedtest.py


words.py: Makefile json2python.py ../src/sqlparse_data.json
	./json2python.py < ../src/sqlparse_data.json > words.py


libinjection/libinjection_wrap.c: libinjection/libinjection.i libinjection/libinjection.h libinjection/libinjection_sqli.h
	swig -version
	swig -python -builtin -Wall -Wextra libinjection/libinjection.i


copy:
	cp ../src/libinjection*.h ../src/libinjection*.c libinjection/

.PHONY: copy

libinjection.so: copy
	gcc -std=c99 -Wall -Werror -fpic -c libinjection/libinjection_sqli.c
	gcc -std=c99 -Wall -Werror -fpic -c libinjection/libinjection_xss.c
	gcc -std=c99 -Wall -Werror -fpic -c libinjection/libinjection_html5.c
	gcc -dynamiclib -shared -o libinjection.so libinjection_sqli.o libinjection_xss.o libinjection_html5.o

clean:
	@rm -rf build dist
	@rm -f *.pyc *~ *.so *.o
	@rm -f nosetests.xml
	@rm -f words.py
	@rm -f libinjection/*~ libinjection/*.pyc
	@rm -f libinjection/libinjection.h libinjection/libinjection_sqli.h libinjection/libinjection_sqli.c libinjection/libinjection_sqli_data.h
	@rm -f libinjection/libinjection_wrap.c libinjection/libinjection.py
