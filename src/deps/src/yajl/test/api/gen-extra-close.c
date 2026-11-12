/* ensure that if we try to generate an extra closing brace
 * we get the expected error */

#include <yajl/yajl_gen.h>
#include <stdio.h>

#define CHK(x) if (x != yajl_gen_status_ok) return 1;

int main(void) {
  yajl_gen yg;
  yajl_gen_status s;

  yg = yajl_gen_alloc(NULL);
  CHK(yajl_gen_map_open(yg));
  CHK(yajl_gen_map_close(yg));
  s = yajl_gen_map_close(yg);

  return (yajl_gen_generation_complete == s);
}
