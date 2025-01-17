LIBINJECTION
==========================

Libinjection is a small C library to detect SQLi attacks in user input with the following goals:

* Open.  Source code is on [GitHub](https://github.com/client9/libinjection/).
* Low _false-positives_.   When there are high false positives, people tend to turn off any WAF or protection.
* Excellent detection of SQLi.
* High performance (currently [over 500,000 TPS](https://libinjection.client9.com/cicada/artifacts/libinjection/libinjection-speed/latest/console.txt))
* Easy to test and QA
* Easy to integrate and extend

### [Try it now](/diagnostics)

### Easy to integrate

* Standard C code, and compiles as C99 and C++, with bindings to
 * [Python](https://github.com/client9/libinjection/wiki/doc-sqli-python)
 * [PHP](https://github.com/client9/libinjection/wiki/doc-sqli-php)
 * [Lua](https://github.com/client9/libinjection/tree/master/lua)
* Small - about [1500 lines of code](https://libinjection.client9.com/cicada/artifacts/libinjection/libinjection-loc/latest/console.txt) in three files
* Compiles on Linux/Unix/BSD, Mac and Windows
* No threads used and thread safe
* No recursion
* No (heap) memory allocation
* No extenal library dependencies
* [400+ unit tests](https://github.com/client9/libinjection/tree/master/tests)
* [98% code coverage](https://libinjection.client9.com/cicada/artifacts/libinjection/libinjection-coverage-unittest/latest/lcov-html/libinjection/src/index.html)
* [BSD License](https://github.com/client9/libinjection/blob/master/COPYING)

Third-Party Ports
---------------------

* [java](https://github.com/Kanatoko/libinjection-Java)
* At least two .NET ports exists
* Another python wrapper

Applications
---------------------

* [ModSecurity](http://www.modsecurity.org/) - since 2.7.4 release
* [IronBee](https://www.ironbee.com) - since May 2013
* Proprietary Honeypot
* Proprietary WAF, Russia
* Proprietary WAF, Japan
