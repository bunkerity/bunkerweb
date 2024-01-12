/*
** Definitions for IBM z/Architecture (s390x) CPUs.
** Copyright (C) 2005-2017 Mike Pall. See Copyright Notice in luajit.h
*/

#ifndef _LJ_TARGET_S390X_H
#define _LJ_TARGET_S390X_H

/* -- Registers IDs ------------------------------------------------------- */

#define GPRDEF(_) \
  _(R0) _(R1) _(R2) _(R3) _(R4) _(R5) _(R6) _(R7) \
  _(R8) _(R9) _(R10) _(R11) _(R12) _(R13) _(R14) _(R15)
#define FPRDEF(_) \
  _(F0) _(F1) _(F2) _(F3) \
  _(F4) _(F5) _(F6) _(F7) \
  _(F8) _(F9) _(F10) _(F11) \
  _(F12) _(F13) _(F14) _(F15) 
// TODO: VREG?

#define RIDENUM(name)	RID_##name,

enum {
  GPRDEF(RIDENUM)		/* General-purpose registers (GPRs). */
  FPRDEF(RIDENUM)		/* Floating-point registers (FPRs). */
  RID_MAX,

  /* Calling conventions. */
  RID_SP = RID_R15,
  RID_RET = RID_R2,
  RID_FPRET = RID_F0,

  /* These definitions must match with the *.dasc file(s): */
  RID_BASE = RID_R7,		/* Interpreter BASE. */
  RID_LPC = RID_R9,		/* Interpreter PC. */
  RID_DISPATCH = RID_R10,	/* Interpreter DISPATCH table. */

  /* Register ranges [min, max) and number of registers. */
  RID_MIN_GPR = RID_R0,
  RID_MIN_FPR = RID_F0,
  RID_MAX_GPR = RID_MIN_FPR,
  RID_MAX_FPR = RID_MAX,
  RID_NUM_GPR = RID_MAX_GPR - RID_MIN_GPR,
  RID_NUM_FPR = RID_MAX_FPR - RID_MIN_FPR,
};

/* -- Register sets ------------------------------------------------------- */

/* -- Spill slots --------------------------------------------------------- */

/* Spill slots are 32 bit wide. An even/odd pair is used for FPRs.
**
** SPS_FIXED: Available fixed spill slots in interpreter frame.
** This definition must match with the *.dasc file(s).
**
** SPS_FIRST: First spill slot for general use. Reserve min. two 32 bit slots.
*/
#define SPS_FIXED	2
#define SPS_FIRST	2

#define SPOFS_TMP	0

#define sps_scale(slot)		(4 * (int32_t)(slot))
#define sps_align(slot)		(((slot) - SPS_FIXED + 1) & ~1)

/* -- Exit state ---------------------------------------------------------- */

/* This definition must match with the *.dasc file(s). */
typedef struct {
  lua_Number fpr[RID_NUM_FPR];	/* Floating-point registers. */
  int32_t gpr[RID_NUM_GPR];	/* General-purpose registers. */
  int32_t spill[256];		/* Spill slots. */
} ExitState;

#define EXITSTUB_SPACING        4
#define EXITSTUBS_PER_GROUP     32

/* -- Instructions -------------------------------------------------------- */

#endif

