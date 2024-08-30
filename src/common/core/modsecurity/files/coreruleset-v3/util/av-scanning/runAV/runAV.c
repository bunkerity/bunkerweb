#include "common.h"

main(int argc, char *argv[])
{
	char cmd[MAX_OUTPUT_SIZE];
	char output[MAX_OUTPUT_SIZE];
	int error;
	char *colon;
	char *keyword;

	if (argc > 1) {
		sprintf (cmd, "/usr/bin/clamscan --no-summary %s", argv[1]);
		output[0] = '\0';
		error = run_cmd(cmd,output,MAX_OUTPUT_SIZE);
		if (error != 0) {
			printf ("1 exec error %d: OK", error);
		} else if (!*output) {
			printf ("1 exec empty: OK");
		}
		else {
		    colon = strstr(output, ":");
		    if (colon) { colon += 2; }
			if (!colon) {
				printf ("0 unable to parse clamscan output [%s] for cmd [%s]", output, cmd);
			}
			else if (keyword = strstr(colon, " FOUND")) {
				*keyword = '\0';
				printf ("0 clamscan: %s", colon);
			}
			else if (keyword = strstr(colon, " ERROR")) {
				*keyword = '\0';
				printf ("0 clamscan: %s", colon);
			}
			else if (keyword = strstr(colon, "OK")) {
				printf ("1 clamscan: OK");
			}
			else if (keyword = strstr(colon, "Empty file")) {
				printf ("1 empty file");
			}
			else if (keyword = strstr(colon, "Can't access file ")) {
				printf ("0 invalid file %s", keyword+18);
			}
			else {
				printf ("0 unable to parse clamscan output [%s] for cmd [%s]", output, cmd);
			}
		}
	}
}
