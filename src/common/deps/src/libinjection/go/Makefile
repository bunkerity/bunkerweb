all: buildgo

.PHONY: buildgo
buildgo: buildlibinjection
	go build main.go	
	@echo "Run ./main"
	
.PHONY: copylibinjection
copylibinjection:
	mkdir libinjection
	cp ../src/libinjection*.h ./libinjection
	cp ../src/libinjection*.c ./libinjection

buildlibinjection: copylibinjection
	gcc -std=c99 -Wall -Werror -fpic -c libinjection/libinjection_sqli.c -o libinjection/libinjection_sqli.o 
	gcc -std=c99 -Wall -Werror -fpic -c libinjection/libinjection_xss.c -o libinjection/libinjection_xss.o
	gcc -std=c99 -Wall -Werror -fpic -c libinjection/libinjection_html5.c -o libinjection/libinjection_html5.o
	gcc -dynamiclib -shared -o libinjection/libinjection.so libinjection/libinjection_sqli.o libinjection/libinjection_xss.o libinjection/libinjection_html5.o 

clean:
	@rm -rf libinjection
	@rm -f main
