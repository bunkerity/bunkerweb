#include "tap.h"

int main () {
    plan(3);
    like("strange", "range", "strange ~~ /range/");
    unlike("strange", "anger", "strange !~~ /anger/");
    like("stranger", "^s.(r).*$", "matches the regex");
    done_testing();
}

