#include "tap.h"
#include <stdio.h>
#include <dirent.h>
#include <stdlib.h>
#include <string.h>

int main () {
    DIR *dp = opendir("t");
    if (!dp) {
        perror("opendir");
        exit(1);
    }
    struct dirent *ep;
    while ((ep = readdir(dp))) {
        char *name = ep->d_name;
        if (strchr(name, '.') || !strcmp(name, "test"))
            continue;
        char command[1024];
        snprintf(command, 1024, "./t/%s >t/%s.got 2>&1", name, name);
        system(command);
        snprintf(command, 1024, "diff -up t/%s.expected t/%s.got", name, name);
        int retval = system(command);
        ok(!(retval >> 8), name);
    }
    closedir(dp);
    done_testing();
}

