#include <assert.h>
#include <stdio.h>
#include <sys/mman.h>

#include "../dasm_proto.h"
#include "../dasm_s390x.h"

// DynASM directives.
|.arch s390x
|.actionlist actions
|.globals lab_

static void add(dasm_State *state)
{
  dasm_State ** Dst = &state;

  | ar r2,r3
  | br r14
}

/*
static void add_rrd(dasm_State *state)
{
  dasm_State **Dst = &state;
  
  | lgfi r4 , 0x02
  | maer r2 , r3 , r4
  | br r14
}
*/

static void sub(dasm_State *state)
{
  dasm_State **Dst = &state;

  | sr r2,r3
  | br r14
}

static void mul(dasm_State *state)
{
  dasm_State **Dst = &state;

  | msr r2 , r3
  | br r14
}

static void rx(dasm_State *state)
{
  dasm_State **Dst = &state;

  int x = 1;
  int y = 4095;

  | la r4, 4095(r2, r3)
  | la r5, 4095(r4)
  | la r1, x(r5)
  | la r2, y(r1, r0)
  | br r14
}

static void rxy(dasm_State *state)
{
  dasm_State **Dst = &state;

  int x = -524287;
  int y = 524286;

  | lay r4, -524288(r2, r3)
  | lay r5, 524287(r4)
  | lay r1, x(r5)
  | lay r2, y(r1, r0)
  | br r14
}

static void lab(dasm_State *state)
{
  dasm_State **Dst = &state;

  // r1 = 0; do { r2 += r2; r1 += 1; } while(r1 < r3);
  | la r1, 0(r0)
  |1:
  | agr r2, r2
  | la r1, 1(r1)
  | cgr r1, r3
  | jl <1
  | br r14
}

static void labg(dasm_State *state)
{
  dasm_State **Dst = &state;

  // r1 = 0; do { r2 += r2; r1 += 1; } while(r1 < r3);
  | la r1, 0(r0)
  |1:
  | agr r2, r2
  | la r1, 1(r1)
  | cgr r1, r3
  | jgl <1
  | jgnl >1
  | stg r0, 0(r0)
  |1:
  | br r14
}

static void jmp_fwd(dasm_State *state)
{
  dasm_State **Dst = &state;
  
  // while(r2!=r3){r2 += 2};
  | j >1
  |1:
  | cgr r2 , r3
  | jne >2
  | je >3
  |2:
  | afi r2, 0x2
  | j <1
  |3:
  | br r14

}

static void add_imm16(dasm_State *state)
{
  dasm_State **Dst = &state;
  
  | ahi r2 , 0xf
  | br r14
}

static void add_imm32(dasm_State *state)
{
  dasm_State **Dst = &state;
  
  | afi r2 , 0xe
  | br r14
}

static void save(dasm_State *state)
{
  dasm_State **Dst = &state;

  |.define CFRAME_SPACE,	224	// Delta for sp, 8 byte aligned.
  |
  |// Register save area.
  |.define SAVE_GPRS,	264(sp)	// Save area for r6-r15 (10*8 bytes).
  |
  |// Argument save area, each slot is 8-bytes (32-bit types are sign/zero extended).
  |.define RESERVED,	232(sp)	// Reserved for compiler use.
  |.define BACKCHAIN,	224(sp)
  |
  |// Current stack frame.
  |.define SAVE_FPR15,	216(sp)
  |.define SAVE_FPR14,	208(sp)
  |.define SAVE_FPR13,	200(sp)
  |.define SAVE_FPR12,	192(sp)
  |.define SAVE_FPR11,	184(sp)
  |.define SAVE_FPR10,	176(sp)
  |.define SAVE_FPR9,	168(sp)
  |.define SAVE_FPR8,	160(sp)
  |
  |// Callee save area.
  |.define CALLEESAVE,	000(sp)
  |
  |.macro saveregs
  |  lay sp, -CFRAME_SPACE(sp)	// Allocate stack frame.
  |  stmg r6, r15, SAVE_GPRS	// Technically we restore r15 regardless.
  |  std f8, SAVE_FPR8		// f8-f15 are callee-saved.
  |  std f9, SAVE_FPR9
  |  std f10, SAVE_FPR10
  |  std f11, SAVE_FPR11
  |  std f12, SAVE_FPR12
  |  std f13, SAVE_FPR13
  |  std f14, SAVE_FPR14
  |  std f15, SAVE_FPR15
  |.endmacro
  |
  |.macro restoreregs
  |  ld f8, SAVE_FPR8		// f8-f15 are callee-saved.
  |  ld f9, SAVE_FPR9
  |  ld f10, SAVE_FPR10
  |  ld f11, SAVE_FPR11
  |  ld f12, SAVE_FPR12
  |  ld f13, SAVE_FPR13
  |  ld f14, SAVE_FPR14
  |  ld f15, SAVE_FPR15
  |  lmg r6, r15, SAVE_GPRS	// Restores the stack pointer.
  |.endmacro
  |
  | saveregs
  | lgfi r7, 0x10 // 16
  | lgfi r8, 0x20 // 32
  | agr r2, r3
  | agr r7, r8
  | msgr r2, r7
  | restoreregs
  | br r14
}

static void labmul(dasm_State *state)
{
  dasm_State **Dst = &state;

  // Multiply using an add function.
  // Only correct if input is positive.
  |->mul_func:
  | stmg r6, r14, 48(sp)
  | lgr r6, r2
  | lgr r7, r3
  | cgfi r7, 0
  | je >3
  | cgfi r7, 1
  | je >2
  |1:
  | lgr r3, r6
  | brasl r14, ->add_func
  | lay r7, -1(r7)
  | cgfi r7, 1
  | jh <1
  |2:
  | lmg r6, r14, 48(sp)
  | br r14
  |3:
  | la r2, 0(r0)
  | j <2

  |->add_func:
  | agr r2, r3
  | br r14
}

static void pc(dasm_State *state) {
  dasm_State **Dst = &state;
  int MAX = 10;
  dasm_growpc(Dst, MAX+1);

  | j =>MAX
  for (int i = 0; i <= MAX; i++) {
    |=>i:
    if (i == 0) {
      | br r14
    } else {
      | aghi r2, i
      | j =>i-1
    }
  }
}

/*
static void load_test(dasm_State *state)
{
  dasm_State **Dst = &state;
  
  | ltdr r2 , r3
  | br r14
}
*/


static void test_mask(dasm_State *state)
{
  dasm_State **Dst = &state;

  |lay   sp , -8(sp)
  |stg   r2,  4(sp)
  |tm    4(sp),0x04
  |je >2
  |jne >1
|1:
  |ar r2,r3
  |br r14
|2:
  |sr r2,r3
  |br r14
}

static void ssa(dasm_State *state) {
  dasm_State **Dst = &state;

  | lay sp, -16(sp)
  | lay r0, -1(r0)
  | stg r0, 8(sp)
  | xc 8(8, sp), 8(sp)
  | stg r2, 0(sp)
  | mvc 13(2, sp), 6(sp)
  | lg r2, 8(sp)
  | la sp, 16(sp)
  | br r14
}

static void ssa_act(dasm_State *state) {
  dasm_State **Dst = &state;

  int xl = 8;
  int d1 = 13;
  int l1 = 2;
  int d2 = 6;

  | lay sp, -16(sp)
  | lay r0, -1(r0)
  | stg r0, 8(sp)
  | xc 8(xl, sp), 8(sp)
  | stg r2, 0(sp)
  | mvc d1(l1, sp), d2(sp)
  | lg r2, 8(sp)
  | la sp, 16(sp)
  | br r14
}

typedef struct {
  int a;
  int b;
} SimpleStruct;

static void type(dasm_State *state) {
  dasm_State **Dst = &state;

  | .type SIMPLE, SimpleStruct
  | lay sp, -8(sp)
  | stg r2, 0(sp)
  | xgr r2, r2
  | l r2, SIMPLE:sp->b
  | la sp, 8(sp)
  | br r14
}

static void sil(dasm_State *state) {
  dasm_State **Dst = &state;

  | lay sp, -16(sp)
  | xc 0(16, sp), 0(sp)
  | mvghi 0(sp), 5
  | mvhi 8(sp), 7
  | mvhhi 12(sp), 11
  | lghi r2, 0
  | ag r2, 0(sp)  // r2 += 5
  | a r2, 8(sp)   // r2 += 7
  | ah r2, 12(sp) // r2 += 11
  | la sp, 16(sp)
  | br r14
}

static void rrfe_rrd(dasm_State *state) {
  dasm_State ** Dst = &state;

  | cefbr f0,r2
  | cefbr f2,r3
  | cefbr f4,r4
  | maebr f0 ,f2 ,f4
  | cfebr r2, 0, f0
  | br r14
}

static void rre(dasm_State *state)  {

  dasm_State **Dst = &state;

  | lay   sp , -8(sp)
  | cefbr f0 ,  r2
  | cefbr f1 ,  r3
  | fidr  f0 ,  f1
  | cfebr r2 ,0,f0
  | la    sp,   8(sp)
  | br   r14
}

static void rsb(dasm_State *state) {
  dasm_State **Dst = &state;

  | lay sp, -4(sp)
  | lghi r3, 0x0706
  | lghi r4, 0
  | iill r4, 6
  | iilh r4, 7
  | st r4, 0(sp)
  | lghi r2, 0
  | clm r3, 5, 0(sp)
  | jne >1
  | lghi r2, 1
  |1:
  | la sp, 4(sp)
  | br r14
}

static void sqrt_rxe(dasm_State *state)
{
  dasm_State **Dst = &state;

  | lay     sp , -8(sp)
  | cefbr   f0 , r2
  | stdy    f0 , 0(sp)
  | sqeb    f0 ,0(r4,sp)
  | cfebr   r2 ,0, f0
  | la      sp, 8(sp)
  | br      r14

}

static void rxf(dasm_State *state) {
  dasm_State **Dst = &state;

  | lay    sp , -8(sp)
  | cegbra f1 ,0, r2,0
  | cegbra f2 ,0,r3,0
  | ste    f2 ,0(sp)
  | maeb   f1, f2, 0(sp)
  | cfebr  r2 ,0, f1
  | la     sp, 8(sp)
  | br     r14

}

typedef struct {
  int64_t arg1;
  int64_t arg2;
  int64_t arg3;
  void (*fn)(dasm_State *);
  int64_t want;
  const char *testname;
} test_table;

test_table test[] = {
  { 1, 2, 0,       add,        3,     "add"},
  {10, 5, 0,       sub,        5,     "sub"},
  { 2, 3, 0,       mul,        6,     "mul"},
  { 5, 7, 0,        rx,    12298,      "rx"},
  { 5, 7, 0,       rxy,       10,     "rxy"},
  { 2, 4, 0,       lab,       32,     "lab"},
  { 2, 4, 0,      labg,       32,    "labg"},
  { 2, 0, 0, add_imm16,       17,   "imm16"},
  { 2, 0, 0, add_imm32,       16,   "imm32"},
  { 7, 3, 0,      save,      480,    "save"},
  { 7, 3, 0,    labmul,       21, "labmul0"},
  { 7, 0, 0,    labmul,        0, "labmul1"},
  { 0, 0, 0,        pc,       55,      "pc"},
  { 2,12, 0,   jmp_fwd,       12, "jmp_fwd"},
//  { 9,8, 0,    add_rrd,       25, "add_rrd"},
//  { 2,4, 0,  load_test,        4,"load_test"},
  {-1, 0, 0,       ssa, 65535<<8,     "ssa"},
  {-1, 0, 0,   ssa_act, 65535<<8, "ssa_act"},
  {27, 0, 0,      type,       27,    "type"},
  { 0, 0, 0,       sil,       23,     "sil"},
  {15, 3,10,   rrfe_rrd,      45, "rrfe_rrd"},
  { 0, 0, 0,        rsb,       0,     "rsb"},
  {12,10, 0,        rre,      10,     "rre"},
  {16,10, 0,   sqrt_rxe,       4,"sqrt_rxe"},
  {16,10, 0,        rxf,     116,     "rxf"},
  { 4, 3, 0,  test_mask,       1,"test_mask"}
};

static void *jitcode(dasm_State **state, size_t *size)
{
  int dasm_status = dasm_link(state, size);
  assert(dasm_status == DASM_S_OK);

  void *ret = mmap(0, *size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
  dasm_encode(state, ret);
  dasm_free(state);

  mprotect(ret, *size, PROT_READ | PROT_EXEC);
  return (int *)ret;
}

int main(int argc, char *argv[])
{
  dasm_State *state;
  for(int i = 0; i < sizeof(test)/sizeof(test[0]); i++) {
    dasm_init(&state, 1);
    void* labels[lab__MAX];
    dasm_setupglobal(&state, labels, lab__MAX);
    dasm_setup(&state, actions);
    test[i].fn(state);
    size_t size;
    int64_t (*fptr)(int64_t, int64_t, int64_t) = jitcode(&state, &size);
    int64_t got = fptr(test[i].arg1, test[i].arg2, test[i].arg3);

    if (got != test[i].want) {
      fprintf(stderr, "FAIL: test %s: want %ld, got %ld\n", test[i].testname, test[i].want, got);
      exit(1);
    }
    munmap(fptr, size);
  }
  printf("all tests passed\n");
  return 0;
}

