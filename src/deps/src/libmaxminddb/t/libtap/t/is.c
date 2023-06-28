#include "tap.h"

int main () {
    plan(18);
    is("this", "that", "this is that"); /* bang */
    is("this", "this", "this is this");
    is("this", "that"); /* bang */
    is("this", "this");
    is(NULL, NULL, "null is null");
    is(NULL, "this", "null is this"); /* bang */
    is("this", NULL, "this is null"); /* bang */
    is("foo\nfoo\nfoo", "bar\nbar\nbar"); /* bang */
    is("foo\nfoo\nfoo", "foo\nfoo\nfoo");
    isnt("this", "that", "this isnt that");
    isnt("this", "this", "this isnt this"); /* bang */
    isnt("this", "that");
    isnt("this", "this"); /* bang */
    isnt(NULL, NULL, "null isnt null"); /* bang */
    isnt(NULL, "this", "null isnt this");
    isnt("this", NULL, "this isnt null");
    isnt("foo\nfoo\nfoo", "bar\nbar\nbar");
    isnt("foo\nfoo\nfoo", "foo\nfoo\nfoo"); /* bang */
    done_testing();
}
