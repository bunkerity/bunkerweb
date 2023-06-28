#include "tap.h"

int main () {
    unsigned char all_0[] = {0, 0, 0, 0};
    unsigned char all_255[] = {255, 255, 255, 255};
    unsigned char half[] = {0, 0, 255, 255};
    unsigned char half_2[] = {0, 0, 255, 255};

    plan(8);
    cmp_mem(half, half_2, 4, "Same array different address");
    cmp_mem(all_0, all_0, 4, "Array must be equal to itself");
    cmp_mem(all_0, all_255, 4, "Arrays with different contents");
    cmp_mem(all_0, half, 4, "Arrays differ, but start the same");
    cmp_mem(all_0, all_255, 0, "Comparing 0 bytes of different arrays");
    cmp_mem(NULL, all_0, 4, "got == NULL");
    cmp_mem(all_0, NULL, 4, "expected == NULL");
    cmp_mem(NULL, NULL, 4, "got == expected == NULL");
    done_testing();
}

