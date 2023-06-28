#include "tap.h"

int main () {
    diag("diag no new line");
    diag("diag new line\n");
    diag("");
    diag(NULL);
    return 1;
}

