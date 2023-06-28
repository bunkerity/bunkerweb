NAME
====

libtap - Write tests in C

SYNOPSIS
========

    #include <tap.h>

    int main () {
        plan(5);
        int bronze = 1, silver = 2, gold = 3;
        ok(bronze < silver, "bronze is less than silver");
        ok(bronze > silver, "not quite");
        is("gold", "gold", "gold is gold");
        cmp_ok(silver, "<", gold, "%d <= %d", silver, gold);
        like("platinum", ".*inum", "platinum matches .*inum");
        done_testing();
    }

results in:

    1..5
    ok 1 - bronze is less than silver
    not ok 2 - not quite
    #   Failed test 'not quite'
    #   at t/synopsis.c line 7.
    ok 3 - gold is gold
    ok 4 - 2 <= 3
    ok 5 - platinum matches .*inum
    # Looks like you failed 1 test of 5 run.

DESCRIPTION
===========

tap is an easy to read and easy to write way of creating tests for
your software. This library creates functions that can be used to
generate it for your C programs. It is implemented using macros
that include file and line info automatically, and makes it so that
the format message of each test is optional. It is mostly based on
the Test::More Perl module.

INSTALL
=======

On **Unix** systems:

    $ make
    $ make install

For more detailed installation instructions (eg, for **Windows**), see `INSTALL`.

FUNCTIONS
=========

-   plan(tests)
-   plan(NO_PLAN)
-   plan(SKIP_ALL);
-   plan(SKIP_ALL, fmt, ...)

    Use this to start a series of tests. When you know how many tests there
    will be, you can put a number as a number of tests you expect to run. If
    you do not know how many tests there will be, you can use plan(NO_PLAN)
    or not call this function. When you pass it a number of tests to run, a
    message similar to the following will appear in the output:

        1..5

    If you pass it SKIP_ALL, the whole test will be skipped.

-   ok(test)
-   ok(test, fmt, ...)

    Specify a test. the test can be any statement returning a true or false
    value. You may optionally pass a format string describing the test.

        ok(r = reader_new("Of Mice and Men"), "create a new reader");
        ok(reader_go_to_page(r, 55), "can turn the page");
        ok(r->page == 55, "page turned to the right one");

    Should print out:

        ok 1 - create a new reader
        ok 2 - can turn the page
        ok 3 - page turned to the right one

    On failure, a diagnostic message will be printed out.

        not ok 3 - page turned to the right one
        #   Failed test 'page turned to the right one'
        #   at reader.c line 13.

-   is(got, expected)
-   is(got, expected, fmt, ...)
-   isnt(got, unexpected)
-   isnt(got, unexpected, fmt, ...)

    Tests that the string you got is what you expected. with isnt, it is the
    reverse.

        is("this", "that", "this is that");

    prints:

        not ok 1 - this is that
        #   Failed test 'this is that'
        #   at is.c line 6.
        #          got: 'this'
        #     expected: 'that'

-   cmp_ok(a, op, b)
-   cmp_ok(a, op, b, fmt, ...)

    Compares two ints with any binary operator that doesn't require an lvalue.
    This is nice to use since it provides a better error message than an
    equivalent ok.

        cmp_ok(420, ">", 666);

    prints:

        not ok 1
        #   Failed test at cmpok.c line 5.
        #     420
        #         >
        #     666

-   cmp_mem(got, expected, n)
-   cmp_mem(got, expected, n, fmt, ...)

    Tests that the first n bytes of the memory you got is what you expected.
    NULL pointers for got and expected are handled (if either is NULL,
    the test fails), but you need to ensure n is not too large.

        char *a = "foo";
        char *b = "bar";
        cmp_mem(a, b, 3)

    prints

        not ok 1
        #   Failed test at t/cmp_mem.c line 9.
        #     Difference starts at offset 0
        #          got: 0x66
        #     expected: 0x62

-   like(got, expected)
-   like(got, expected, fmt, ...)
-   unlike(got, unexpected)
-   unlike(got, unexpected, fmt, ...)

    Tests that the string you got matches the expected extended POSIX regex.
    unlike is the reverse. These macros are the equivalent of a skip on
    Windows.

        like("stranger", "^s.(r).*\\1$", "matches the regex");

    prints:

        ok 1 - matches the regex

-   pass()
-   pass(fmt, ...)
-   fail()
-   fail(fmt, ...)

    Speciy that a test succeeded or failed. Use these when the statement is
    longer than you can fit into the argument given to an ok() test.

-   dies_ok(code)
-   dies_ok(code, fmt, ...)
-   lives_ok(code)
-   lives_ok(code, fmt, ...)

    Tests whether the given code causes your program to exit. The code gets
    passed to a macro that will test it in a forked process. If the code
    succeeds it will be executed in the parent process. You can test things
    like passing a function a null pointer and make sure it doesnt
    dereference it and crash.

        dies_ok({abort();}, "abort does close your program");
        dies_ok({int x = 0/0;}, "divide by zero crash");
        lives_ok({pow(3.0, 5.0);}, "nothing wrong with taking 3**5");

    On Windows, these macros are the equivalent of a skip.

-   done_testing()

    Summarizes the tests that occurred and exits the main function. If
    there was no plan, it will print out the number of tests as.

        1..5

    It will also print a diagnostic message about how many
    failures there were.

        # Looks like you failed 2 tests of 3 run.

    If all planned tests were successful, it will return 0. If any
    test fails, it will return 1. If they all passed, but there
    were missing tests, it will return 2.

-   diag(fmt, ...)

    print out a message to the tap output on stdout. Each line is
    preceeded by a "# " so that you know its a diagnostic message.

        diag("This is\na diag\nto describe\nsomething.");

    prints:

        # This is
        # a diag
        # to describe
        # something

    ok() and this function return an int so you can use it like:

        ok(0) || diag("doh!");

-   skip(test, n)
-   skip(test, n, fmt, ...)
-   end_skip

    Skip a series of n tests if test is true. You may give a reason why you are
    skipping them or not. The (possibly) skipped tests must occur between the
    skip and end_skip macros.

        skip(TRUE, 2);
        ok(1);
        ok(0);
        end_skip;

    prints:

        ok 1 # skip
        ok 2 # skip

-   todo()
-   todo(fmt, ...)
-   end_todo

    Specifies a series of tests that you expect to fail because they are not
    yet implemented.

        todo()
        ok(0);
        end_todo;

    prints:

        not ok 1 # TODO
        #   Failed (TODO) test at todo.c line 7

-   BAIL_OUT()
-   BAIL_OUT(fmt, ...)

    Immediately stops all testing.

        BAIL_OUT("Can't go no further");

    prints

        Bail out!  Can't go no further

    and exits with 255.

