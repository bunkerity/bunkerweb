#include "tap.h"

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

