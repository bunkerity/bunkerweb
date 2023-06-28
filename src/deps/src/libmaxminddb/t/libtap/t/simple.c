#include "tap.h"

int main () {
    plan(24);
    ok(1);
    ok(1);
    ok(1);
    ok(0);
    ok(1, "foo");
    ok(1, "bar");
    ok(1, "baz");
    ok(1, "quux");
    ok(1, "thud");
    ok(1, "wombat");
    ok(1, "blurgle");
    ok(1, "frob");
    ok(0, "frobnicate");
    ok(1, "eek");
    ok(1, "ook");
    ok(1, "frodo");
    ok(1, "bilbo");
    ok(1, "wubble");
    ok(1, "flarp");
    ok(1, "fnord");
    pass();
    fail();
    pass("good");
    fail("bad");
    done_testing();
}

