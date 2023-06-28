#include "tap.h"

int main () {
    plan(6);
    todo();
    ok(0, "foo");
    ok(1, "bar");
    ok(1, "baz");
    end_todo;
    todo("im not ready");
    ok(0, "quux");
    ok(1, "thud");
    ok(1, "wombat");
    end_todo;
    done_testing();
}

