#include "tap.h"

int main () {
    plan(8);
    skip(0, 3, "%s cannot fork", "windows");
    ok(1, "quux");
    ok(1, "thud");
    ok(1, "wombat");
    end_skip;
    skip(1, 1, "need to be on windows");
    ok(0, "blurgle");
    end_skip;
    skip(0, 3);
    ok(1, "quux");
    ok(1, "thud");
    ok(1, "wombat");
    end_skip;
    skip(1, 1);
    ok(0, "blurgle");
    end_skip;
    done_testing();
}

