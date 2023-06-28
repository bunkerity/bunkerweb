#include "tap.h"

int main () {
    plan(5);
    ok(1, "sanity");
    dies_ok({int x = 0; x = 1/x;}, "can't divide by zero");
    lives_ok({int x = 3; x = x/7;}, "this is a perfectly fine statement");
    dies_ok({abort();}, "abort kills the program");
    dies_ok(
        {printf("stdout\n"); fprintf(stderr, "stderr\n"); abort();},
        "supress output");
    done_testing();
}

