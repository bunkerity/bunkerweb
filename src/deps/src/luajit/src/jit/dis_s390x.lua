----------------------------------------------------------------------------
-- LuaJIT s390x disassembler module.
--
-- Copyright (C) 2005-2022 Mike Pall. All rights reserved.
-- Released under the MIT license. See Copyright Notice in luajit.h
--
-- Contributed by Aditya Bisht from Open Mainframe.
----------------------------------------------------------------------------
-- This is a helper module used by the LuaJIT machine code dumper module.
--
-- NYI: 
------------------------------------------------------------------------------

local type = type
local sub, byte, format = string.sub, string.byte, string.format
local match, gmatch, gsub = string.match, string.gmatch, string.gsub
local lower, rep = string.lower, string.rep
local bit = require("bit")
local band, lshift, bor, rshift = bit.band, bit.lshift, bit.bor, bit.rshift
local tohex = bit.tohex

local ONELONG = "%08lx: "

local OPERAND_GPR = 	0x1	/* Operand printed as %rx */
local OPERAND_FPR = 	0x2	/* Operand printed as %fx */
local OPERAND_AR =  	0x4	/* Operand printed as %ax */
local OPERAND_CR =  	0x8	/* Operand printed as %cx */
local OPERAND_DISP =	0x10	/* Operand printed as displacement */
local OPERAND_BASE =	0x20	/* Operand printed as base register */
local OPERAND_INDEX =	0x40	/* Operand printed as index register */
local OPERAND_PCREL =	0x80	/* Operand printed as pc-relative symbol */
local OPERAND_SIGNED =	0x100	/* Operand printed as signed value */
local OPERAND_LENGTH =	0x200	/* Operand printed as length (+1) */

-- Registers

local UNUSED = 0,	/* Indicates the end of the operand list */
local R_8 = 1,	/* GPR starting at position 8 */
local R_12 = 2,	/* GPR starting at position 12 */
local R_16 = 3,	/* GPR starting at position 16 */
local R_20 = 4,	/* GPR starting at position 20 */
local R_24 = 5,	/* GPR starting at position 24 */
local R_28 = 6,	/* GPR starting at position 28 */
local R_32 = 7,	/* GPR starting at position 32 */
local F_8 = 8,	/* FPR starting at position 8 */
local F_12 = 9,	/* FPR starting at position 12 */
local F_16 = 10,	/* FPR starting at position 16 */
local F_20 = 11,	/* FPR starting at position 16 */
local F_24 = 12,	/* FPR starting at position 24 */
local F_28 = 13,	/* FPR starting at position 28 */
local F_32 = 14,	/* FPR starting at position 32 */
local A_8 = 15,	/* Access reg. starting at position 8 */
local A_12 = 16,	/* Access reg. starting at position 12 */
local A_24 = 17,	/* Access reg. starting at position 24 */
local A_28 = 18,	/* Access reg. starting at position 28 */
local C_8 = 19,	/* Control reg. starting at position 8 */
local C_12 = 20,	/* Control reg. starting at position 12 */
local B_16 = 21,	/* Base register starting at position 16 */
local B_32 = 22,	/* Base register starting at position 32 */
local X_12 = 23,	/* Index register starting at position 12 */
local D_20 = 24,	/* Displacement starting at position 20 */
local D_36 = 25,	/* Displacement starting at position 36 */
local D20_20 = 26,	/* 20 bit displacement starting at 20 */
local L4_8 = 27,	/* 4 bit length starting at position 8 */
local L4_12 = 28,	/* 4 bit length starting at position 12 */
local L8_8 = 29,	/* 8 bit length starting at position 8 */
local U4_8 = 30,	/* 4 bit unsigned value starting at 8 */
local U4_12 = 31,	/* 4 bit unsigned value starting at 12 */
local U4_16 = 32,	/* 4 bit unsigned value starting at 16 */
local U4_20 = 33,	/* 4 bit unsigned value starting at 20 */
local U4_32 = 34,	/* 4 bit unsigned value starting at 32 */
local U8_8 = 35,	/* 8 bit unsigned value starting at 8 */
local U8_16 = 36,	/* 8 bit unsigned value starting at 16 */
local U8_24 = 37,	/* 8 bit unsigned value starting at 24 */
local U8_32 = 38,	/* 8 bit unsigned value starting at 32 */
local I8_8 = 39,	/* 8 bit signed value starting at 8 */
local I8_32 = 40,	/* 8 bit signed value starting at 32 */
local I16_16 = 41,	/* 16 bit signed value starting at 16 */
local I16_32 = 42,	/* 32 bit signed value starting at 16 */
local U16_16 = 43,	/* 16 bit unsigned value starting at 16 */
local U16_32 = 44,	/* 32 bit unsigned value starting at 16 */
local J16_16 = 45,	/* PC relative jump offset at 16 */
local J32_16 = 46,	/* PC relative long offset at 16 */
local I32_16 = 47,	/* 32 bit signed value starting at 16 */
local U32_16 = 48,	/* 32 bit unsigned value starting at 16 */
local M_16 = 49,	/* 4 bit optional mask starting at 16 */
local RO_28 = 50	/* optional GPR starting at position 28 */

-- Enumeration of the different instruction formats.
-- For details consult the principles of operation.

local INSTR_INVALID = 1,
local INSTR_E = 2,
local INSTR_RIE_R0IU = 3,
local INSTR_RIE_R0UU = 4,
local INSTR_RIE_RRP = 5,
local INSTR_RIE_RRPU = 6,
local INSTR_RIE_RRUUU = 7,
local INSTR_RIE_RUPI = 8,
local INSTR_RIE_RUPU = 9,
local INSTR_RIL_RI = 10,
local INSTR_RIL_RP = 11,
local INSTR_RIL_RU = 12,
local INSTR_RIL_UP = 13,
local INSTR_RIS_R0RDU = 14,
local INSTR_RIS_R0UU = 15,
local INSTR_RIS_RURDI = 16,
local INSTR_RIS_RURDU = 17,
local INSTR_RI_RI = 18,
local INSTR_RI_RP = 19,
local INSTR_RI_RU = 20,
local INSTR_RI_UP = 21,
local INSTR_RRE_00 = 22,
local INSTR_RRE_0R = 23,
local INSTR_RRE_AA = 24,
local INSTR_RRE_AR = 25,
local INSTR_RRE_F0 = 26,
local INSTR_RRE_FF = 27,
local INSTR_RRE_FR = 28,
local INSTR_RRE_R0 = 29,
local INSTR_RRE_RA = 30,
local INSTR_RRE_RF = 31,
local INSTR_RRE_RR = 32,
local INSTR_RRE_RR_OPT = 33,
local INSTR_RRF_0UFF = 34,
local INSTR_RRF_F0FF = 35,
local INSTR_RRF_F0FF2 = 36,
local INSTR_RRF_F0FR = 37,
local INSTR_RRF_FFRU = 38,
local INSTR_RRF_FUFF = 39,
local INSTR_RRF_M0RR = 40,
local INSTR_RRF_R0RR = 41,
local INSTR_RRF_RURR = 42,
local INSTR_RRF_U0FF = 43,
local INSTR_RRF_U0RF = 44,
local INSTR_RRF_U0RR = 45,
local INSTR_RRF_UUFF = 46,
local INSTR_RRR_F0FF = 47,
local INSTR_RRS_RRRDU = 48,
local INSTR_RR_FF = 49,
local INSTR_RR_R0 = 50,
local INSTR_RR_RR = 51,
local INSTR_RR_U0 = 52,
local INSTR_RR_UR = 53,
local INSTR_RSE_CCRD = 54,
local INSTR_RSE_RRRD = 55,
local INSTR_RSE_RURD = 56,
local INSTR_RSI_RRP = 57,
local INSTR_RSL_R0RD = 58,
local INSTR_RSY_AARD = 59,
local INSTR_RSY_CCRD = 60,
local INSTR_RSY_RRRD = 61,
local INSTR_RSY_RURD = 62,
local INSTR_RS_AARD = 63,
local INSTR_RS_CCRD = 64,
local INSTR_RS_R0RD = 65,
local INSTR_RS_RRRD = 66,
local INSTR_RS_RURD = 67,
local INSTR_RXE_FRRD = 68,
local INSTR_RXE_RRRD = 69,
local INSTR_RXF_FRRDF = 70,
local INSTR_RXY_FRRD = 71,
local INSTR_RXY_RRRD = 72,
local INSTR_RXY_URRD = 73,
local INSTR_RX_FRRD = 74,
local INSTR_RX_RRRD = 75,
local INSTR_RX_URRD = 76,
local INSTR_SIL_RDI = 77,
local INSTR_SIL_RDU = 78,
local INSTR_SIY_IRD = 79,
local INSTR_SIY_URD = 80,
local INSTR_SI_URD = 81,
local INSTR_SSE_RDRD = 82,
local INSTR_SSF_RRDRD = 83,
local INSTR_SS_L0RDRD = 84,
local INSTR_SS_LIRDRD = 85,
local INSTR_SS_LLRDRD = 86,
local INSTR_SS_RRRDRD = 87,
local INSTR_SS_RRRDRD2 = 88,
local INSTR_SS_RRRDRD3 = 89,
local INSTR_S_00 = 90,
local INSTR_S_RD = 91

local operands = {
    [UNUSED]  = { 0, 0, 0 },
	[R_8]	 = {  4,  8, OPERAND_GPR },
	[R_12]	 = {  4, 12, OPERAND_GPR },
	[R_16]	 = {  4, 16, OPERAND_GPR },
	[R_20]	 = {  4, 20, OPERAND_GPR },
	[R_24]	 = {  4, 24, OPERAND_GPR },
	[R_28]	 = {  4, 28, OPERAND_GPR },
	[R_32]	 = {  4, 32, OPERAND_GPR },
	[F_8]	 = {  4,  8, OPERAND_FPR },
	[F_12]	 = {  4, 12, OPERAND_FPR },
	[F_16]	 = {  4, 16, OPERAND_FPR },
	[F_20]	 = {  4, 16, OPERAND_FPR },
	[F_24]	 = {  4, 24, OPERAND_FPR },
	[F_28]	 = {  4, 28, OPERAND_FPR },
	[F_32]	 = {  4, 32, OPERAND_FPR },
	[A_8]	 = {  4,  8, OPERAND_AR },
	[A_12]	 = {  4, 12, OPERAND_AR },
	[A_24]	 = {  4, 24, OPERAND_AR },
	[A_28]	 = {  4, 28, OPERAND_AR },
	[C_8]	 = {  4,  8, OPERAND_CR },
	[C_12]	 = {  4, 12, OPERAND_CR },
	[B_16]	 = {  4, 16, OPERAND_BASE | OPERAND_GPR },
	[B_32]	 = {  4, 32, OPERAND_BASE | OPERAND_GPR },
	[X_12]	 = {  4, 12, OPERAND_INDEX | OPERAND_GPR },
	[D_20]	 = { 12, 20, OPERAND_DISP },
	[D_36]	 = { 12, 36, OPERAND_DISP },
	[D20_20] = { 20, 20, OPERAND_DISP | OPERAND_SIGNED },
	[L4_8]	 = {  4,  8, OPERAND_LENGTH },
	[L4_12]  = {  4, 12, OPERAND_LENGTH },
	[L8_8]	 = {  8,  8, OPERAND_LENGTH },
	[U4_8]	 = {  4,  8, 0 },
	[U4_12]  = {  4, 12, 0 },
	[U4_16]  = {  4, 16, 0 },
	[U4_20]  = {  4, 20, 0 },
	[U4_32]  = {  4, 32, 0 },
	[U8_8]	 = {  8,  8, 0 },
	[U8_16]  = {  8, 16, 0 },
	[U8_24]  = {  8, 24, 0 },
	[U8_32]  = {  8, 32, 0 },
	[I16_16] = { 16, 16, OPERAND_SIGNED },
	[U16_16] = { 16, 16, 0 },
	[U16_32] = { 16, 32, 0 },
	[J16_16] = { 16, 16, OPERAND_PCREL },
	[I16_32] = { 16, 32, OPERAND_SIGNED },
	[J32_16] = { 32, 16, OPERAND_PCREL },
	[I32_16] = { 32, 16, OPERAND_SIGNED },
	[U32_16] = { 32, 16, 0 },
	[M_16]	 = {  4, 16, 0 },
	[RO_28]  = {  4, 28, OPERAND_GPR }
}

local formats = {
    [INSTR_E]	  = { 0xff, 0,0,0,0,0,0 },
	[INSTR_RIE_R0UU]  = { 0xff, R_8,U16_16,U4_32,0,0,0 },
	[INSTR_RIE_RRPU]  = { 0xff, R_8,R_12,U4_32,J16_16,0,0 },
	[INSTR_RIE_RRP]	  = { 0xff, R_8,R_12,J16_16,0,0,0 },
	[INSTR_RIE_RRUUU] = { 0xff, R_8,R_12,U8_16,U8_24,U8_32,0 },
	[INSTR_RIE_RUPI]  = { 0xff, R_8,I8_32,U4_12,J16_16,0,0 },
	[INSTR_RIL_RI]	  = { 0x0f, R_8,I32_16,0,0,0,0 },
	[INSTR_RIL_RP]	  = { 0x0f, R_8,J32_16,0,0,0,0 },
	[INSTR_RIL_RU]	  = { 0x0f, R_8,U32_16,0,0,0,0 },
	[INSTR_RIL_UP]	  = { 0x0f, U4_8,J32_16,0,0,0,0 },
	[INSTR_RIS_R0RDU] = { 0xff, R_8,U8_32,D_20,B_16,0,0 },
	[INSTR_RIS_RURDI] = { 0xff, R_8,I8_32,U4_12,D_20,B_16,0 },
	[INSTR_RIS_RURDU] = { 0xff, R_8,U8_32,U4_12,D_20,B_16,0 },
	[INSTR_RI_RI]	  = { 0x0f, R_8,I16_16,0,0,0,0 },
	[INSTR_RI_RP]	  = { 0x0f, R_8,J16_16,0,0,0,0 },
	[INSTR_RI_RU]	  = { 0x0f, R_8,U16_16,0,0,0,0 },
	[INSTR_RI_UP]	  = { 0x0f, U4_8,J16_16,0,0,0,0 },
	[INSTR_RRE_00]	  = { 0xff, 0,0,0,0,0,0 },
	[INSTR_RRE_0R]	  = { 0xff, R_28,0,0,0,0,0 },
	[INSTR_RRE_AA]	  = { 0xff, A_24,A_28,0,0,0,0 },
	[INSTR_RRE_AR]	  = { 0xff, A_24,R_28,0,0,0,0 },
	[INSTR_RRE_F0]	  = { 0xff, F_24,0,0,0,0,0 },
	[INSTR_RRE_FF]	  = { 0xff, F_24,F_28,0,0,0,0 },
	[INSTR_RRE_FR]	  = { 0xff, F_24,R_28,0,0,0,0 },
	[INSTR_RRE_R0]	  = { 0xff, R_24,0,0,0,0,0 },
	[INSTR_RRE_RA]	  = { 0xff, R_24,A_28,0,0,0,0 },
	[INSTR_RRE_RF]	  = { 0xff, R_24,F_28,0,0,0,0 },
	[INSTR_RRE_RR]	  = { 0xff, R_24,R_28,0,0,0,0 },
	[INSTR_RRE_RR_OPT]= { 0xff, R_24,RO_28,0,0,0,0 },
	[INSTR_RRF_0UFF]  = { 0xff, F_24,F_28,U4_20,0,0,0 },
	[INSTR_RRF_F0FF2] = { 0xff, F_24,F_16,F_28,0,0,0 },
	[INSTR_RRF_F0FF]  = { 0xff, F_16,F_24,F_28,0,0,0 },
	[INSTR_RRF_F0FR]  = { 0xff, F_24,F_16,R_28,0,0,0 },
	[INSTR_RRF_FFRU]  = { 0xff, F_24,F_16,R_28,U4_20,0,0 },
	[INSTR_RRF_FUFF]  = { 0xff, F_24,F_16,F_28,U4_20,0,0 },
	[INSTR_RRF_M0RR]  = { 0xff, R_24,R_28,M_16,0,0,0 },
	[INSTR_RRF_R0RR]  = { 0xff, R_24,R_16,R_28,0,0,0 },
	[INSTR_RRF_RURR]  = { 0xff, R_24,R_28,R_16,U4_20,0,0 },
	[INSTR_RRF_U0FF]  = { 0xff, F_24,U4_16,F_28,0,0,0 },
	[INSTR_RRF_U0RF]  = { 0xff, R_24,U4_16,F_28,0,0,0 },
	[INSTR_RRF_U0RR]  = { 0xff, R_24,R_28,U4_16,0,0,0 },
	[INSTR_RRF_UUFF]  = { 0xff, F_24,U4_16,F_28,U4_20,0,0 },
	[INSTR_RRR_F0FF]  = { 0xff, F_24,F_28,F_16,0,0,0 },
	[INSTR_RRS_RRRDU] = { 0xff, R_8,R_12,U4_32,D_20,B_16,0 },
	[INSTR_RR_FF]	  = { 0xff, F_8,F_12,0,0,0,0 },
	[INSTR_RR_R0]	  = { 0xff, R_8, 0,0,0,0,0 },
	[INSTR_RR_RR]	  = { 0xff, R_8,R_12,0,0,0,0 },
	[INSTR_RR_U0]	  = { 0xff, U8_8, 0,0,0,0,0 },
	[INSTR_RR_UR]	  = { 0xff, U4_8,R_12,0,0,0,0 },
	[INSTR_RSE_CCRD]  = { 0xff, C_8,C_12,D_20,B_16,0,0 },
	[INSTR_RSE_RRRD]  = { 0xff, R_8,R_12,D_20,B_16,0,0 },
	[INSTR_RSE_RURD]  = { 0xff, R_8,U4_12,D_20,B_16,0,0 },
	[INSTR_RSI_RRP]	  = { 0xff, R_8,R_12,J16_16,0,0,0 },
	[INSTR_RSL_R0RD]  = { 0xff, D_20,L4_8,B_16,0,0,0 },
	[INSTR_RSY_AARD]  = { 0xff, A_8,A_12,D20_20,B_16,0,0 },
	[INSTR_RSY_CCRD]  = { 0xff, C_8,C_12,D20_20,B_16,0,0 },
	[INSTR_RSY_RRRD]  = { 0xff, R_8,R_12,D20_20,B_16,0,0 },
	[INSTR_RSY_RURD]  = { 0xff, R_8,U4_12,D20_20,B_16,0,0 },
	[INSTR_RS_AARD]	  = { 0xff, A_8,A_12,D_20,B_16,0,0 },
	[INSTR_RS_CCRD]	  = { 0xff, C_8,C_12,D_20,B_16,0,0 },
	[INSTR_RS_R0RD]	  = { 0xff, R_8,D_20,B_16,0,0,0 },
	[INSTR_RS_RRRD]	  = { 0xff, R_8,R_12,D_20,B_16,0,0 },
	[INSTR_RS_RURD]	  = { 0xff, R_8,U4_12,D_20,B_16,0,0 },
	[INSTR_RXE_FRRD]  = { 0xff, F_8,D_20,X_12,B_16,0,0 },
	[INSTR_RXE_RRRD]  = { 0xff, R_8,D_20,X_12,B_16,0,0 },
	[INSTR_RXF_FRRDF] = { 0xff, F_32,F_8,D_20,X_12,B_16,0 },
	[INSTR_RXY_FRRD]  = { 0xff, F_8,D20_20,X_12,B_16,0,0 },
	[INSTR_RXY_RRRD]  = { 0xff, R_8,D20_20,X_12,B_16,0,0 },
	[INSTR_RXY_URRD]  = { 0xff, U4_8,D20_20,X_12,B_16,0,0 },
	[INSTR_RX_FRRD]	  = { 0xff, F_8,D_20,X_12,B_16,0,0 },
	[INSTR_RX_RRRD]	  = { 0xff, R_8,D_20,X_12,B_16,0,0 },
	[INSTR_RX_URRD]	  = { 0xff, U4_8,D_20,X_12,B_16,0,0 },
	[INSTR_SIL_RDI]   = { 0xff, D_20,B_16,I16_32,0,0,0 },
	[INSTR_SIL_RDU]   = { 0xff, D_20,B_16,U16_32,0,0,0 },
	[INSTR_SIY_IRD]   = { 0xff, D20_20,B_16,I8_8,0,0,0 },
	[INSTR_SIY_URD]	  = { 0xff, D20_20,B_16,U8_8,0,0,0 },
	[INSTR_SI_URD]	  = { 0xff, D_20,B_16,U8_8,0,0,0 },
	[INSTR_SSE_RDRD]  = { 0xff, D_20,B_16,D_36,B_32,0,0 },
	[INSTR_SSF_RRDRD] = { 0x00, D_20,B_16,D_36,B_32,R_8,0 },
	[INSTR_SS_L0RDRD] = { 0xff, D_20,L8_8,B_16,D_36,B_32,0 },
	[INSTR_SS_LIRDRD] = { 0xff, D_20,L4_8,B_16,D_36,B_32,U4_12 },
	[INSTR_SS_LLRDRD] = { 0xff, D_20,L4_8,B_16,D_36,L4_12,B_32 },
	[INSTR_SS_RRRDRD2]= { 0xff, R_8,D_20,B_16,R_12,D_36,B_32 },
	[INSTR_SS_RRRDRD3]= { 0xff, R_8,R_12,D_20,B_16,D_36,B_32 },
	[INSTR_SS_RRRDRD] = { 0xff, D_20,R_8,B_16,D_36,B_32,R_12 },
	[INSTR_S_00]	  = { 0xff, 0,0,0,0,0,0 },
	[INSTR_S_RD]	  = { 0xff, D_20,B_16,0,0,0,0 },
}

local opcode = {
    { "lmd", 0xef, INSTR_SS_RRRDRD3 },
    { "spm", 0x04, INSTR_RR_R0 },
	{ "balr", 0x05, INSTR_RR_RR },
	{ "bctr", 0x06, INSTR_RR_RR },
	{ "bcr", 0x07, INSTR_RR_UR },
	{ "svc", 0x0a, INSTR_RR_U0 },
	{ "bsm", 0x0b, INSTR_RR_RR },
	{ "bassm", 0x0c, INSTR_RR_RR },
	{ "basr", 0x0d, INSTR_RR_RR },
	{ "mvcl", 0x0e, INSTR_RR_RR },
	{ "clcl", 0x0f, INSTR_RR_RR },
	{ "lpr", 0x10, INSTR_RR_RR },
	{ "lnr", 0x11, INSTR_RR_RR },
	{ "ltr", 0x12, INSTR_RR_RR },
	{ "lcr", 0x13, INSTR_RR_RR },
	{ "nr", 0x14, INSTR_RR_RR },
	{ "clr", 0x15, INSTR_RR_RR },
	{ "or", 0x16, INSTR_RR_RR },
	{ "xr", 0x17, INSTR_RR_RR },
	{ "lr", 0x18, INSTR_RR_RR },
	{ "cr", 0x19, INSTR_RR_RR },
	{ "ar", 0x1a, INSTR_RR_RR },
	{ "sr", 0x1b, INSTR_RR_RR },
	{ "mr", 0x1c, INSTR_RR_RR },
	{ "dr", 0x1d, INSTR_RR_RR },
	{ "alr", 0x1e, INSTR_RR_RR },
	{ "slr", 0x1f, INSTR_RR_RR },
	{ "lpdr", 0x20, INSTR_RR_FF },
	{ "lndr", 0x21, INSTR_RR_FF },
	{ "ltdr", 0x22, INSTR_RR_FF },
	{ "lcdr", 0x23, INSTR_RR_FF },
	{ "hdr", 0x24, INSTR_RR_FF },
	{ "ldxr", 0x25, INSTR_RR_FF },
	{ "lrdr", 0x25, INSTR_RR_FF },
	{ "mxr", 0x26, INSTR_RR_FF },
	{ "mxdr", 0x27, INSTR_RR_FF },
	{ "ldr", 0x28, INSTR_RR_FF },
	{ "cdr", 0x29, INSTR_RR_FF },
	{ "adr", 0x2a, INSTR_RR_FF },
	{ "sdr", 0x2b, INSTR_RR_FF },
	{ "mdr", 0x2c, INSTR_RR_FF },
	{ "ddr", 0x2d, INSTR_RR_FF },
	{ "awr", 0x2e, INSTR_RR_FF },
	{ "swr", 0x2f, INSTR_RR_FF },
	{ "lper", 0x30, INSTR_RR_FF },
	{ "lner", 0x31, INSTR_RR_FF },
	{ "lter", 0x32, INSTR_RR_FF },
	{ "lcer", 0x33, INSTR_RR_FF },
	{ "her", 0x34, INSTR_RR_FF },
	{ "ledr", 0x35, INSTR_RR_FF },
	{ "lrer", 0x35, INSTR_RR_FF },
	{ "axr", 0x36, INSTR_RR_FF },
	{ "sxr", 0x37, INSTR_RR_FF },
	{ "ler", 0x38, INSTR_RR_FF },
	{ "cer", 0x39, INSTR_RR_FF },
	{ "aer", 0x3a, INSTR_RR_FF },
	{ "ser", 0x3b, INSTR_RR_FF },
	{ "mder", 0x3c, INSTR_RR_FF },
	{ "mer", 0x3c, INSTR_RR_FF },
	{ "der", 0x3d, INSTR_RR_FF },
	{ "aur", 0x3e, INSTR_RR_FF },
	{ "sur", 0x3f, INSTR_RR_FF },
	{ "sth", 0x40, INSTR_RX_RRRD },
	{ "la", 0x41, INSTR_RX_RRRD },
	{ "stc", 0x42, INSTR_RX_RRRD },
	{ "ic", 0x43, INSTR_RX_RRRD },
	{ "ex", 0x44, INSTR_RX_RRRD },
	{ "bal", 0x45, INSTR_RX_RRRD },
	{ "bct", 0x46, INSTR_RX_RRRD },
	{ "bc", 0x47, INSTR_RX_URRD },
	{ "lh", 0x48, INSTR_RX_RRRD },
	{ "ch", 0x49, INSTR_RX_RRRD },
	{ "ah", 0x4a, INSTR_RX_RRRD },
	{ "sh", 0x4b, INSTR_RX_RRRD },
	{ "mh", 0x4c, INSTR_RX_RRRD },
	{ "bas", 0x4d, INSTR_RX_RRRD },
	{ "cvd", 0x4e, INSTR_RX_RRRD },
	{ "cvb", 0x4f, INSTR_RX_RRRD },
	{ "st", 0x50, INSTR_RX_RRRD },
	{ "lae", 0x51, INSTR_RX_RRRD },
	{ "n", 0x54, INSTR_RX_RRRD },
	{ "cl", 0x55, INSTR_RX_RRRD },
	{ "o", 0x56, INSTR_RX_RRRD },
	{ "x", 0x57, INSTR_RX_RRRD },
	{ "l", 0x58, INSTR_RX_RRRD },
	{ "c", 0x59, INSTR_RX_RRRD },
	{ "a", 0x5a, INSTR_RX_RRRD },
	{ "s", 0x5b, INSTR_RX_RRRD },
	{ "m", 0x5c, INSTR_RX_RRRD },
	{ "d", 0x5d, INSTR_RX_RRRD },
	{ "al", 0x5e, INSTR_RX_RRRD },
	{ "sl", 0x5f, INSTR_RX_RRRD },
	{ "std", 0x60, INSTR_RX_FRRD },
	{ "mxd", 0x67, INSTR_RX_FRRD },
	{ "ld", 0x68, INSTR_RX_FRRD },
	{ "cd", 0x69, INSTR_RX_FRRD },
	{ "ad", 0x6a, INSTR_RX_FRRD },
	{ "sd", 0x6b, INSTR_RX_FRRD },
	{ "md", 0x6c, INSTR_RX_FRRD },
	{ "dd", 0x6d, INSTR_RX_FRRD },
	{ "aw", 0x6e, INSTR_RX_FRRD },
	{ "sw", 0x6f, INSTR_RX_FRRD },
	{ "ste", 0x70, INSTR_RX_FRRD },
	{ "ms", 0x71, INSTR_RX_RRRD },
	{ "le", 0x78, INSTR_RX_FRRD },
	{ "ce", 0x79, INSTR_RX_FRRD },
	{ "ae", 0x7a, INSTR_RX_FRRD },
	{ "se", 0x7b, INSTR_RX_FRRD },
	{ "mde", 0x7c, INSTR_RX_FRRD },
	{ "me", 0x7c, INSTR_RX_FRRD },
	{ "de", 0x7d, INSTR_RX_FRRD },
	{ "au", 0x7e, INSTR_RX_FRRD },
	{ "su", 0x7f, INSTR_RX_FRRD },
	{ "ssm", 0x80, INSTR_S_RD },
	{ "lpsw", 0x82, INSTR_S_RD },
	{ "diag", 0x83, INSTR_RS_RRRD },
	{ "brxh", 0x84, INSTR_RSI_RRP },
	{ "brxle", 0x85, INSTR_RSI_RRP },
	{ "bxh", 0x86, INSTR_RS_RRRD },
	{ "bxle", 0x87, INSTR_RS_RRRD },
	{ "srl", 0x88, INSTR_RS_R0RD },
	{ "sll", 0x89, INSTR_RS_R0RD },
	{ "sra", 0x8a, INSTR_RS_R0RD },
	{ "sla", 0x8b, INSTR_RS_R0RD },
	{ "srdl", 0x8c, INSTR_RS_R0RD },
	{ "sldl", 0x8d, INSTR_RS_R0RD },
	{ "srda", 0x8e, INSTR_RS_R0RD },
	{ "slda", 0x8f, INSTR_RS_R0RD },
	{ "stm", 0x90, INSTR_RS_RRRD },
	{ "tm", 0x91, INSTR_SI_URD },
	{ "mvi", 0x92, INSTR_SI_URD },
	{ "ts", 0x93, INSTR_S_RD },
	{ "ni", 0x94, INSTR_SI_URD },
	{ "cli", 0x95, INSTR_SI_URD },
	{ "oi", 0x96, INSTR_SI_URD },
	{ "xi", 0x97, INSTR_SI_URD },
	{ "lm", 0x98, INSTR_RS_RRRD },
	{ "trace", 0x99, INSTR_RS_RRRD },
	{ "lam", 0x9a, INSTR_RS_AARD },
	{ "stam", 0x9b, INSTR_RS_AARD },
	{ "mvcle", 0xa8, INSTR_RS_RRRD },
	{ "clcle", 0xa9, INSTR_RS_RRRD },
	{ "stnsm", 0xac, INSTR_SI_URD },
	{ "stosm", 0xad, INSTR_SI_URD },
	{ "sigp", 0xae, INSTR_RS_RRRD },
	{ "mc", 0xaf, INSTR_SI_URD },
	{ "lra", 0xb1, INSTR_RX_RRRD },
	{ "stctl", 0xb6, INSTR_RS_CCRD },
	{ "lctl", 0xb7, INSTR_RS_CCRD },
	{ "cs", 0xba, INSTR_RS_RRRD },
	{ "cds", 0xbb, INSTR_RS_RRRD },
	{ "clm", 0xbd, INSTR_RS_RURD },
	{ "stcm", 0xbe, INSTR_RS_RURD },
	{ "icm", 0xbf, INSTR_RS_RURD },
	{ "mvn", 0xd1, INSTR_SS_L0RDRD },
	{ "mvc", 0xd2, INSTR_SS_L0RDRD },
	{ "mvz", 0xd3, INSTR_SS_L0RDRD },
	{ "nc", 0xd4, INSTR_SS_L0RDRD },
	{ "clc", 0xd5, INSTR_SS_L0RDRD },
	{ "oc", 0xd6, INSTR_SS_L0RDRD },
	{ "xc", 0xd7, INSTR_SS_L0RDRD },
	{ "mvck", 0xd9, INSTR_SS_RRRDRD },
	{ "mvcp", 0xda, INSTR_SS_RRRDRD },
	{ "mvcs", 0xdb, INSTR_SS_RRRDRD },
	{ "tr", 0xdc, INSTR_SS_L0RDRD },
	{ "trt", 0xdd, INSTR_SS_L0RDRD },
	{ "ed", 0xde, INSTR_SS_L0RDRD },
	{ "edmk", 0xdf, INSTR_SS_L0RDRD },
	{ "pku", 0xe1, INSTR_SS_L0RDRD },
	{ "unpku", 0xe2, INSTR_SS_L0RDRD },
	{ "mvcin", 0xe8, INSTR_SS_L0RDRD },
	{ "pka", 0xe9, INSTR_SS_L0RDRD },
	{ "unpka", 0xea, INSTR_SS_L0RDRD },
	{ "plo", 0xee, INSTR_SS_RRRDRD2 },
	{ "srp", 0xf0, INSTR_SS_LIRDRD },
	{ "mvo", 0xf1, INSTR_SS_LLRDRD },
	{ "pack", 0xf2, INSTR_SS_LLRDRD },
	{ "unpk", 0xf3, INSTR_SS_LLRDRD },
	{ "zap", 0xf8, INSTR_SS_LLRDRD },
	{ "cp", 0xf9, INSTR_SS_LLRDRD },
	{ "ap", 0xfa, INSTR_SS_LLRDRD },
	{ "sp", 0xfb, INSTR_SS_LLRDRD },
	{ "mp", 0xfc, INSTR_SS_LLRDRD },
	{ "dp", 0xfd, INSTR_SS_LLRDRD },
	{ "", 0, INSTR_INVALID }
}

local opcode_01 = {
    { "sam64", 0x0e, INSTR_E },
	{ "pfpo", 0x0a, INSTR_E },
	{ "ptff", 0x04, INSTR_E },
    { "pr", 0x01, INSTR_E },
	{ "upt", 0x02, INSTR_E },
	{ "sckpf", 0x07, INSTR_E },
	{ "tam", 0x0b, INSTR_E },
	{ "sam24", 0x0c, INSTR_E },
	{ "sam31", 0x0d, INSTR_E },
	{ "trap2", 0xff, INSTR_E },
	{ "", 0, INSTR_INVALID }
}

local opcode_a5 = {
    { "iihh", 0x00, INSTR_RI_RU },
	{ "iihl", 0x01, INSTR_RI_RU },
	{ "iilh", 0x02, INSTR_RI_RU },
	{ "iill", 0x03, INSTR_RI_RU },
	{ "nihh", 0x04, INSTR_RI_RU },
	{ "nihl", 0x05, INSTR_RI_RU },
	{ "nilh", 0x06, INSTR_RI_RU },
	{ "nill", 0x07, INSTR_RI_RU },
	{ "oihh", 0x08, INSTR_RI_RU },
	{ "oihl", 0x09, INSTR_RI_RU },
	{ "oilh", 0x0a, INSTR_RI_RU },
	{ "oill", 0x0b, INSTR_RI_RU },
	{ "llihh", 0x0c, INSTR_RI_RU },
	{ "llihl", 0x0d, INSTR_RI_RU },
	{ "llilh", 0x0e, INSTR_RI_RU },
	{ "llill", 0x0f, INSTR_RI_RU },
    { "", 0, INSTR_INVALID }
}

local opcode_a7 = {
    { "tmhh", 0x02, INSTR_RI_RU },
	{ "tmhl", 0x03, INSTR_RI_RU },
	{ "brctg", 0x07, INSTR_RI_RP },
	{ "lghi", 0x09, INSTR_RI_RI },
	{ "aghi", 0x0b, INSTR_RI_RI },
	{ "mghi", 0x0d, INSTR_RI_RI },
	{ "cghi", 0x0f, INSTR_RI_RI },
    { "tmlh", 0x00, INSTR_RI_RU },
	{ "tmll", 0x01, INSTR_RI_RU },
	{ "brc", 0x04, INSTR_RI_UP },
	{ "bras", 0x05, INSTR_RI_RP },
	{ "brct", 0x06, INSTR_RI_RP },
	{ "lhi", 0x08, INSTR_RI_RI },
	{ "ahi", 0x0a, INSTR_RI_RI },
	{ "mhi", 0x0c, INSTR_RI_RI },
	{ "chi", 0x0e, INSTR_RI_RI },
	{ "", 0, INSTR_INVALID }
}

local opcode_b2 = {
    { "sske", 0x2b, INSTR_RRF_M0RR },
	{ "stckf", 0x7c, INSTR_S_RD },
	{ "cu21", 0xa6, INSTR_RRF_M0RR },
	{ "cuutf", 0xa6, INSTR_RRF_M0RR },
	{ "cu12", 0xa7, INSTR_RRF_M0RR },
	{ "cutfu", 0xa7, INSTR_RRF_M0RR },
	{ "stfle", 0xb0, INSTR_S_RD },
	{ "lpswe", 0xb2, INSTR_S_RD },
	{ "srnmt", 0xb9, INSTR_S_RD },
	{ "lfas", 0xbd, INSTR_S_RD },
    { "stidp", 0x02, INSTR_S_RD },
	{ "sck", 0x04, INSTR_S_RD },
	{ "stck", 0x05, INSTR_S_RD },
	{ "sckc", 0x06, INSTR_S_RD },
	{ "stckc", 0x07, INSTR_S_RD },
	{ "spt", 0x08, INSTR_S_RD },
	{ "stpt", 0x09, INSTR_S_RD },
	{ "spka", 0x0a, INSTR_S_RD },
	{ "ipk", 0x0b, INSTR_S_00 },
	{ "ptlb", 0x0d, INSTR_S_00 },
	{ "spx", 0x10, INSTR_S_RD },
	{ "stpx", 0x11, INSTR_S_RD },
	{ "stap", 0x12, INSTR_S_RD },
	{ "sie", 0x14, INSTR_S_RD },
	{ "pc", 0x18, INSTR_S_RD },
	{ "sac", 0x19, INSTR_S_RD },
	{ "cfc", 0x1a, INSTR_S_RD },
	{ "ipte", 0x21, INSTR_RRE_RR },
	{ "ipm", 0x22, INSTR_RRE_R0 },
	{ "ivsk", 0x23, INSTR_RRE_RR },
	{ "iac", 0x24, INSTR_RRE_R0 },
	{ "ssar", 0x25, INSTR_RRE_R0 },
	{ "epar", 0x26, INSTR_RRE_R0 },
	{ "esar", 0x27, INSTR_RRE_R0 },
	{ "pt", 0x28, INSTR_RRE_RR },
	{ "iske", 0x29, INSTR_RRE_RR },
	{ "rrbe", 0x2a, INSTR_RRE_RR },
	{ "sske", 0x2b, INSTR_RRE_RR },
	{ "tb", 0x2c, INSTR_RRE_0R },
	{ "dxr", 0x2d, INSTR_RRE_F0 },
	{ "pgin", 0x2e, INSTR_RRE_RR },
	{ "pgout", 0x2f, INSTR_RRE_RR },
	{ "csch", 0x30, INSTR_S_00 },
	{ "hsch", 0x31, INSTR_S_00 },
	{ "msch", 0x32, INSTR_S_RD },
	{ "ssch", 0x33, INSTR_S_RD },
	{ "stsch", 0x34, INSTR_S_RD },
	{ "tsch", 0x35, INSTR_S_RD },
	{ "tpi", 0x36, INSTR_S_RD },
	{ "sal", 0x37, INSTR_S_00 },
	{ "rsch", 0x38, INSTR_S_00 },
	{ "stcrw", 0x39, INSTR_S_RD },
	{ "stcps", 0x3a, INSTR_S_RD },
	{ "rchp", 0x3b, INSTR_S_00 },
	{ "schm", 0x3c, INSTR_S_00 },
	{ "bakr", 0x40, INSTR_RRE_RR },
	{ "cksm", 0x41, INSTR_RRE_RR },
	{ "sqdr", 0x44, INSTR_RRE_F0 },
	{ "sqer", 0x45, INSTR_RRE_F0 },
	{ "stura", 0x46, INSTR_RRE_RR },
	{ "msta", 0x47, INSTR_RRE_R0 },
	{ "palb", 0x48, INSTR_RRE_00 },
	{ "ereg", 0x49, INSTR_RRE_RR },
	{ "esta", 0x4a, INSTR_RRE_RR },
	{ "lura", 0x4b, INSTR_RRE_RR },
	{ "tar", 0x4c, INSTR_RRE_AR },
	{ "cpya", 0x4d, INSTR_RRE_AA },
	{ "sar", 0x4e, INSTR_RRE_AR },
	{ "ear", 0x4f, INSTR_RRE_RA },
	{ "csp", 0x50, INSTR_RRE_RR },
	{ "msr", 0x52, INSTR_RRE_RR },
	{ "mvpg", 0x54, INSTR_RRE_RR },
	{ "mvst", 0x55, INSTR_RRE_RR },
	{ "cuse", 0x57, INSTR_RRE_RR },
	{ "bsg", 0x58, INSTR_RRE_RR },
	{ "bsa", 0x5a, INSTR_RRE_RR },
	{ "clst", 0x5d, INSTR_RRE_RR },
	{ "srst", 0x5e, INSTR_RRE_RR },
	{ "cmpsc", 0x63, INSTR_RRE_RR },
	{ "siga", 0x74, INSTR_S_RD },
	{ "xsch", 0x76, INSTR_S_00 },
	{ "rp", 0x77, INSTR_S_RD },
	{ "stcke", 0x78, INSTR_S_RD },
	{ "sacf", 0x79, INSTR_S_RD },
	{ "stsi", 0x7d, INSTR_S_RD },
	{ "srnm", 0x99, INSTR_S_RD },
	{ "stfpc", 0x9c, INSTR_S_RD },
	{ "lfpc", 0x9d, INSTR_S_RD },
	{ "tre", 0xa5, INSTR_RRE_RR },
	{ "cuutf", 0xa6, INSTR_RRE_RR },
	{ "cutfu", 0xa7, INSTR_RRE_RR },
	{ "stfl", 0xb1, INSTR_S_RD },
	{ "trap4", 0xff, INSTR_S_RD },
	{ "", 0, INSTR_INVALID }
}

local opcode_b3 = {
    { "maylr", 0x38, INSTR_RRF_F0FF },
	{ "mylr", 0x39, INSTR_RRF_F0FF },
	{ "mayr", 0x3a, INSTR_RRF_F0FF },
	{ "myr", 0x3b, INSTR_RRF_F0FF },
	{ "mayhr", 0x3c, INSTR_RRF_F0FF },
	{ "myhr", 0x3d, INSTR_RRF_F0FF },
	{ "cegbr", 0xa4, INSTR_RRE_RR },
	{ "cdgbr", 0xa5, INSTR_RRE_RR },
	{ "cxgbr", 0xa6, INSTR_RRE_RR },
	{ "cgebr", 0xa8, INSTR_RRF_U0RF },
	{ "cgdbr", 0xa9, INSTR_RRF_U0RF },
	{ "cgxbr", 0xaa, INSTR_RRF_U0RF },
	{ "cfer", 0xb8, INSTR_RRF_U0RF },
	{ "cfdr", 0xb9, INSTR_RRF_U0RF },
	{ "cfxr", 0xba, INSTR_RRF_U0RF },
	{ "cegr", 0xc4, INSTR_RRE_RR },
	{ "cdgr", 0xc5, INSTR_RRE_RR },
	{ "cxgr", 0xc6, INSTR_RRE_RR },
	{ "cger", 0xc8, INSTR_RRF_U0RF },
	{ "cgdr", 0xc9, INSTR_RRF_U0RF },
	{ "cgxr", 0xca, INSTR_RRF_U0RF },
	{ "lpdfr", 0x70, INSTR_RRE_FF },
	{ "lndfr", 0x71, INSTR_RRE_FF },
	{ "cpsdr", 0x72, INSTR_RRF_F0FF2 },
	{ "lcdfr", 0x73, INSTR_RRE_FF },
	{ "ldgr", 0xc1, INSTR_RRE_FR },
	{ "lgdr", 0xcd, INSTR_RRE_RF },
	{ "adtr", 0xd2, INSTR_RRR_F0FF },
	{ "axtr", 0xda, INSTR_RRR_F0FF },
	{ "cdtr", 0xe4, INSTR_RRE_FF },
	{ "cxtr", 0xec, INSTR_RRE_FF },
	{ "kdtr", 0xe0, INSTR_RRE_FF },
	{ "kxtr", 0xe8, INSTR_RRE_FF },
	{ "cedtr", 0xf4, INSTR_RRE_FF },
	{ "cextr", 0xfc, INSTR_RRE_FF },
	{ "cdgtr", 0xf1, INSTR_RRE_FR },
	{ "cxgtr", 0xf9, INSTR_RRE_FR },
	{ "cdstr", 0xf3, INSTR_RRE_FR },
	{ "cxstr", 0xfb, INSTR_RRE_FR },
	{ "cdutr", 0xf2, INSTR_RRE_FR },
	{ "cxutr", 0xfa, INSTR_RRE_FR },
	{ "cgdtr", 0xe1, INSTR_RRF_U0RF },
	{ "cgxtr", 0xe9, INSTR_RRF_U0RF },
	{ "csdtr", 0xe3, INSTR_RRE_RF },
	{ "csxtr", 0xeb, INSTR_RRE_RF },
	{ "cudtr", 0xe2, INSTR_RRE_RF },
	{ "cuxtr", 0xea, INSTR_RRE_RF },
	{ "ddtr", 0xd1, INSTR_RRR_F0FF },
	{ "dxtr", 0xd9, INSTR_RRR_F0FF },
	{ "eedtr", 0xe5, INSTR_RRE_RF },
	{ "eextr", 0xed, INSTR_RRE_RF },
	{ "esdtr", 0xe7, INSTR_RRE_RF },
	{ "esxtr", 0xef, INSTR_RRE_RF },
	{ "iedtr", 0xf6, INSTR_RRF_F0FR },
	{ "iextr", 0xfe, INSTR_RRF_F0FR },
	{ "ltdtr", 0xd6, INSTR_RRE_FF },
	{ "ltxtr", 0xde, INSTR_RRE_FF },
	{ "fidtr", 0xd7, INSTR_RRF_UUFF },
	{ "fixtr", 0xdf, INSTR_RRF_UUFF },
	{ "ldetr", 0xd4, INSTR_RRF_0UFF },
	{ "lxdtr", 0xdc, INSTR_RRF_0UFF },
	{ "ledtr", 0xd5, INSTR_RRF_UUFF },
	{ "ldxtr", 0xdd, INSTR_RRF_UUFF },
	{ "mdtr", 0xd0, INSTR_RRR_F0FF },
	{ "mxtr", 0xd8, INSTR_RRR_F0FF },
	{ "qadtr", 0xf5, INSTR_RRF_FUFF },
	{ "qaxtr", 0xfd, INSTR_RRF_FUFF },
	{ "rrdtr", 0xf7, INSTR_RRF_FFRU },
	{ "rrxtr", 0xff, INSTR_RRF_FFRU },
	{ "sfasr", 0x85, INSTR_RRE_R0 },
	{ "sdtr", 0xd3, INSTR_RRR_F0FF },
	{ "sxtr", 0xdb, INSTR_RRR_F0FF },
    { "lpebr", 0x00, INSTR_RRE_FF },
	{ "lnebr", 0x01, INSTR_RRE_FF },
	{ "ltebr", 0x02, INSTR_RRE_FF },
	{ "lcebr", 0x03, INSTR_RRE_FF },
	{ "ldebr", 0x04, INSTR_RRE_FF },
	{ "lxdbr", 0x05, INSTR_RRE_FF },
	{ "lxebr", 0x06, INSTR_RRE_FF },
	{ "mxdbr", 0x07, INSTR_RRE_FF },
	{ "kebr", 0x08, INSTR_RRE_FF },
	{ "cebr", 0x09, INSTR_RRE_FF },
	{ "aebr", 0x0a, INSTR_RRE_FF },
	{ "sebr", 0x0b, INSTR_RRE_FF },
	{ "mdebr", 0x0c, INSTR_RRE_FF },
	{ "debr", 0x0d, INSTR_RRE_FF },
	{ "maebr", 0x0e, INSTR_RRF_F0FF },
	{ "msebr", 0x0f, INSTR_RRF_F0FF },
	{ "lpdbr", 0x10, INSTR_RRE_FF },
	{ "lndbr", 0x11, INSTR_RRE_FF },
	{ "ltdbr", 0x12, INSTR_RRE_FF },
	{ "lcdbr", 0x13, INSTR_RRE_FF },
	{ "sqebr", 0x14, INSTR_RRE_FF },
	{ "sqdbr", 0x15, INSTR_RRE_FF },
	{ "sqxbr", 0x16, INSTR_RRE_FF },
	{ "meebr", 0x17, INSTR_RRE_FF },
	{ "kdbr", 0x18, INSTR_RRE_FF },
	{ "cdbr", 0x19, INSTR_RRE_FF },
	{ "adbr", 0x1a, INSTR_RRE_FF },
	{ "sdbr", 0x1b, INSTR_RRE_FF },
	{ "mdbr", 0x1c, INSTR_RRE_FF },
	{ "ddbr", 0x1d, INSTR_RRE_FF },
	{ "madbr", 0x1e, INSTR_RRF_F0FF },
	{ "msdbr", 0x1f, INSTR_RRF_F0FF },
	{ "lder", 0x24, INSTR_RRE_FF },
	{ "lxdr", 0x25, INSTR_RRE_FF },
	{ "lxer", 0x26, INSTR_RRE_FF },
	{ "maer", 0x2e, INSTR_RRF_F0FF },
	{ "mser", 0x2f, INSTR_RRF_F0FF },
	{ "sqxr", 0x36, INSTR_RRE_FF },
	{ "meer", 0x37, INSTR_RRE_FF },
	{ "madr", 0x3e, INSTR_RRF_F0FF },
	{ "msdr", 0x3f, INSTR_RRF_F0FF },
	{ "lpxbr", 0x40, INSTR_RRE_FF },
	{ "lnxbr", 0x41, INSTR_RRE_FF },
	{ "ltxbr", 0x42, INSTR_RRE_FF },
	{ "lcxbr", 0x43, INSTR_RRE_FF },
	{ "ledbr", 0x44, INSTR_RRE_FF },
	{ "ldxbr", 0x45, INSTR_RRE_FF },
	{ "lexbr", 0x46, INSTR_RRE_FF },
	{ "fixbr", 0x47, INSTR_RRF_U0FF },
	{ "kxbr", 0x48, INSTR_RRE_FF },
	{ "cxbr", 0x49, INSTR_RRE_FF },
	{ "axbr", 0x4a, INSTR_RRE_FF },
	{ "sxbr", 0x4b, INSTR_RRE_FF },
	{ "mxbr", 0x4c, INSTR_RRE_FF },
	{ "dxbr", 0x4d, INSTR_RRE_FF },
	{ "tbedr", 0x50, INSTR_RRF_U0FF },
	{ "tbdr", 0x51, INSTR_RRF_U0FF },
	{ "diebr", 0x53, INSTR_RRF_FUFF },
	{ "fiebr", 0x57, INSTR_RRF_U0FF },
	{ "thder", 0x58, INSTR_RRE_RR },
	{ "thdr", 0x59, INSTR_RRE_RR },
	{ "didbr", 0x5b, INSTR_RRF_FUFF },
	{ "fidbr", 0x5f, INSTR_RRF_U0FF },
	{ "lpxr", 0x60, INSTR_RRE_FF },
	{ "lnxr", 0x61, INSTR_RRE_FF },
	{ "ltxr", 0x62, INSTR_RRE_FF },
	{ "lcxr", 0x63, INSTR_RRE_FF },
	{ "lxr", 0x65, INSTR_RRE_RR },
	{ "lexr", 0x66, INSTR_RRE_FF },
	{ "fixr", 0x67, INSTR_RRF_U0FF },
	{ "cxr", 0x69, INSTR_RRE_FF },
	{ "lzer", 0x74, INSTR_RRE_R0 },
	{ "lzdr", 0x75, INSTR_RRE_R0 },
	{ "lzxr", 0x76, INSTR_RRE_R0 },
	{ "fier", 0x77, INSTR_RRF_U0FF },
	{ "fidr", 0x7f, INSTR_RRF_U0FF },
	{ "sfpc", 0x84, INSTR_RRE_RR_OPT },
	{ "efpc", 0x8c, INSTR_RRE_RR_OPT },
	{ "cefbr", 0x94, INSTR_RRE_RF },
	{ "cdfbr", 0x95, INSTR_RRE_RF },
	{ "cxfbr", 0x96, INSTR_RRE_RF },
	{ "cfebr", 0x98, INSTR_RRF_U0RF },
	{ "cfdbr", 0x99, INSTR_RRF_U0RF },
	{ "cfxbr", 0x9a, INSTR_RRF_U0RF },
	{ "cefr", 0xb4, INSTR_RRE_RF },
	{ "cdfr", 0xb5, INSTR_RRE_RF },
	{ "cxfr", 0xb6, INSTR_RRE_RF },
	{ "", 0, INSTR_INVALID }
}

local opcode_b9 = {
    { "lpgr", 0x00, INSTR_RRE_RR },
	{ "lngr", 0x01, INSTR_RRE_RR },
	{ "ltgr", 0x02, INSTR_RRE_RR },
	{ "lcgr", 0x03, INSTR_RRE_RR },
	{ "lgr", 0x04, INSTR_RRE_RR },
	{ "lurag", 0x05, INSTR_RRE_RR },
	{ "lgbr", 0x06, INSTR_RRE_RR },
	{ "lghr", 0x07, INSTR_RRE_RR },
	{ "agr", 0x08, INSTR_RRE_RR },
	{ "sgr", 0x09, INSTR_RRE_RR },
	{ "algr", 0x0a, INSTR_RRE_RR },
	{ "slgr", 0x0b, INSTR_RRE_RR },
	{ "msgr", 0x0c, INSTR_RRE_RR },
	{ "dsgr", 0x0d, INSTR_RRE_RR },
	{ "eregg", 0x0e, INSTR_RRE_RR },
	{ "lrvgr", 0x0f, INSTR_RRE_RR },
	{ "lpgfr", 0x10, INSTR_RRE_RR },
	{ "lngfr", 0x11, INSTR_RRE_RR },
	{ "ltgfr", 0x12, INSTR_RRE_RR },
	{ "lcgfr", 0x13, INSTR_RRE_RR },
	{ "lgfr", 0x14, INSTR_RRE_RR },
	{ "llgfr", 0x16, INSTR_RRE_RR },
	{ "llgtr", 0x17, INSTR_RRE_RR },
	{ "agfr", 0x18, INSTR_RRE_RR },
	{ "sgfr", 0x19, INSTR_RRE_RR },
	{ "algfr", 0x1a, INSTR_RRE_RR },
	{ "slgfr", 0x1b, INSTR_RRE_RR },
	{ "msgfr", 0x1c, INSTR_RRE_RR },
	{ "dsgfr", 0x1d, INSTR_RRE_RR },
	{ "cgr", 0x20, INSTR_RRE_RR },
	{ "clgr", 0x21, INSTR_RRE_RR },
	{ "sturg", 0x25, INSTR_RRE_RR },
	{ "lbr", 0x26, INSTR_RRE_RR },
	{ "lhr", 0x27, INSTR_RRE_RR },
	{ "cgfr", 0x30, INSTR_RRE_RR },
	{ "clgfr", 0x31, INSTR_RRE_RR },
	{ "bctgr", 0x46, INSTR_RRE_RR },
	{ "ngr", 0x80, INSTR_RRE_RR },
	{ "ogr", 0x81, INSTR_RRE_RR },
	{ "xgr", 0x82, INSTR_RRE_RR },
	{ "flogr", 0x83, INSTR_RRE_RR },
	{ "llgcr", 0x84, INSTR_RRE_RR },
	{ "llghr", 0x85, INSTR_RRE_RR },
	{ "mlgr", 0x86, INSTR_RRE_RR },
	{ "dlgr", 0x87, INSTR_RRE_RR },
	{ "alcgr", 0x88, INSTR_RRE_RR },
	{ "slbgr", 0x89, INSTR_RRE_RR },
	{ "cspg", 0x8a, INSTR_RRE_RR },
	{ "idte", 0x8e, INSTR_RRF_R0RR },
	{ "llcr", 0x94, INSTR_RRE_RR },
	{ "llhr", 0x95, INSTR_RRE_RR },
	{ "esea", 0x9d, INSTR_RRE_R0 },
	{ "lptea", 0xaa, INSTR_RRF_RURR },
	{ "cu14", 0xb0, INSTR_RRF_M0RR },
	{ "cu24", 0xb1, INSTR_RRF_M0RR },
	{ "cu41", 0xb2, INSTR_RRF_M0RR },
	{ "cu42", 0xb3, INSTR_RRF_M0RR },
	{ "crt", 0x72, INSTR_RRF_U0RR },
	{ "cgrt", 0x60, INSTR_RRF_U0RR },
	{ "clrt", 0x73, INSTR_RRF_U0RR },
	{ "clgrt", 0x61, INSTR_RRF_U0RR },
	{ "ptf", 0xa2, INSTR_RRE_R0 },
	{ "pfmf", 0xaf, INSTR_RRE_RR },
	{ "trte", 0xbf, INSTR_RRF_M0RR },
	{ "trtre", 0xbd, INSTR_RRF_M0RR },
    { "kmac", 0x1e, INSTR_RRE_RR },
	{ "lrvr", 0x1f, INSTR_RRE_RR },
	{ "km", 0x2e, INSTR_RRE_RR },
	{ "kmc", 0x2f, INSTR_RRE_RR },
	{ "kimd", 0x3e, INSTR_RRE_RR },
	{ "klmd", 0x3f, INSTR_RRE_RR },
	{ "epsw", 0x8d, INSTR_RRE_RR },
	{ "trtt", 0x90, INSTR_RRE_RR },
	{ "trtt", 0x90, INSTR_RRF_M0RR },
	{ "trto", 0x91, INSTR_RRE_RR },
	{ "trto", 0x91, INSTR_RRF_M0RR },
	{ "trot", 0x92, INSTR_RRE_RR },
	{ "trot", 0x92, INSTR_RRF_M0RR },
	{ "troo", 0x93, INSTR_RRE_RR },
	{ "troo", 0x93, INSTR_RRF_M0RR },
	{ "mlr", 0x96, INSTR_RRE_RR },
	{ "dlr", 0x97, INSTR_RRE_RR },
	{ "alcr", 0x98, INSTR_RRE_RR },
	{ "slbr", 0x99, INSTR_RRE_RR },
	{ "", 0, INSTR_INVALID }
}

local opcode_c0 = {
	{ "lgfi", 0x01, INSTR_RIL_RI },
	{ "xihf", 0x06, INSTR_RIL_RU },
	{ "xilf", 0x07, INSTR_RIL_RU },
	{ "iihf", 0x08, INSTR_RIL_RU },
	{ "iilf", 0x09, INSTR_RIL_RU },
	{ "nihf", 0x0a, INSTR_RIL_RU },
	{ "nilf", 0x0b, INSTR_RIL_RU },
	{ "oihf", 0x0c, INSTR_RIL_RU },
	{ "oilf", 0x0d, INSTR_RIL_RU },
	{ "llihf", 0x0e, INSTR_RIL_RU },
	{ "llilf", 0x0f, INSTR_RIL_RU },
	{ "larl", 0x00, INSTR_RIL_RP },
	{ "brcl", 0x04, INSTR_RIL_UP },
	{ "brasl", 0x05, INSTR_RIL_RP },
	{ "", 0, INSTR_INVALID }
}

local opcode_c2 = {
	{ "slgfi", 0x04, INSTR_RIL_RU },
	{ "slfi", 0x05, INSTR_RIL_RU },
	{ "agfi", 0x08, INSTR_RIL_RI },
	{ "afi", 0x09, INSTR_RIL_RI },
	{ "algfi", 0x0a, INSTR_RIL_RU },
	{ "alfi", 0x0b, INSTR_RIL_RU },
	{ "cgfi", 0x0c, INSTR_RIL_RI },
	{ "cfi", 0x0d, INSTR_RIL_RI },
	{ "clgfi", 0x0e, INSTR_RIL_RU },
	{ "clfi", 0x0f, INSTR_RIL_RU },
	{ "msfi", 0x01, INSTR_RIL_RI },
	{ "msgfi", 0x00, INSTR_RIL_RI },
	{ "", 0, INSTR_INVALID }
}

local opcode_c4 = {
	{ "lrl", 0x0d, INSTR_RIL_RP },
	{ "lgrl", 0x08, INSTR_RIL_RP },
	{ "lgfrl", 0x0c, INSTR_RIL_RP },
	{ "lhrl", 0x05, INSTR_RIL_RP },
	{ "lghrl", 0x04, INSTR_RIL_RP },
	{ "llgfrl", 0x0e, INSTR_RIL_RP },
	{ "llhrl", 0x02, INSTR_RIL_RP },
	{ "llghrl", 0x06, INSTR_RIL_RP },
	{ "strl", 0x0f, INSTR_RIL_RP },
	{ "stgrl", 0x0b, INSTR_RIL_RP },
	{ "sthrl", 0x07, INSTR_RIL_RP },
	{ "", 0, INSTR_INVALID }
}

local opcode_c6 = {
	{ "crl", 0x0d, INSTR_RIL_RP },
	{ "cgrl", 0x08, INSTR_RIL_RP },
	{ "cgfrl", 0x0c, INSTR_RIL_RP },
	{ "chrl", 0x05, INSTR_RIL_RP },
	{ "cghrl", 0x04, INSTR_RIL_RP },
	{ "clrl", 0x0f, INSTR_RIL_RP },
	{ "clgrl", 0x0a, INSTR_RIL_RP },
	{ "clgfrl", 0x0e, INSTR_RIL_RP },
	{ "clhrl", 0x07, INSTR_RIL_RP },
	{ "clghrl", 0x06, INSTR_RIL_RP },
	{ "pfdrl", 0x02, INSTR_RIL_UP },
	{ "exrl", 0x00, INSTR_RIL_RP },
	{ "", 0, INSTR_INVALID }
}

local opcode_c8 = {
	{ "mvcos", 0x00, INSTR_SSF_RRDRD },
	{ "ectg", 0x01, INSTR_SSF_RRDRD },
	{ "csst", 0x02, INSTR_SSF_RRDRD },
	{ "", 0, INSTR_INVALID }
}

local opcode_e3 = {
	{ "ltg", 0x02, INSTR_RXY_RRRD },
	{ "lrag", 0x03, INSTR_RXY_RRRD },
	{ "lg", 0x04, INSTR_RXY_RRRD },
	{ "cvby", 0x06, INSTR_RXY_RRRD },
	{ "ag", 0x08, INSTR_RXY_RRRD },
	{ "sg", 0x09, INSTR_RXY_RRRD },
	{ "alg", 0x0a, INSTR_RXY_RRRD },
	{ "slg", 0x0b, INSTR_RXY_RRRD },
	{ "msg", 0x0c, INSTR_RXY_RRRD },
	{ "dsg", 0x0d, INSTR_RXY_RRRD },
	{ "cvbg", 0x0e, INSTR_RXY_RRRD },
	{ "lrvg", 0x0f, INSTR_RXY_RRRD },
	{ "lt", 0x12, INSTR_RXY_RRRD },
	{ "lray", 0x13, INSTR_RXY_RRRD },
	{ "lgf", 0x14, INSTR_RXY_RRRD },
	{ "lgh", 0x15, INSTR_RXY_RRRD },
	{ "llgf", 0x16, INSTR_RXY_RRRD },
	{ "llgt", 0x17, INSTR_RXY_RRRD },
	{ "agf", 0x18, INSTR_RXY_RRRD },
	{ "sgf", 0x19, INSTR_RXY_RRRD },
	{ "algf", 0x1a, INSTR_RXY_RRRD },
	{ "slgf", 0x1b, INSTR_RXY_RRRD },
	{ "msgf", 0x1c, INSTR_RXY_RRRD },
	{ "dsgf", 0x1d, INSTR_RXY_RRRD },
	{ "cg", 0x20, INSTR_RXY_RRRD },
	{ "clg", 0x21, INSTR_RXY_RRRD },
	{ "stg", 0x24, INSTR_RXY_RRRD },
	{ "cvdy", 0x26, INSTR_RXY_RRRD },
	{ "cvdg", 0x2e, INSTR_RXY_RRRD },
	{ "strvg", 0x2f, INSTR_RXY_RRRD },
	{ "cgf", 0x30, INSTR_RXY_RRRD },
	{ "clgf", 0x31, INSTR_RXY_RRRD },
	{ "strvh", 0x3f, INSTR_RXY_RRRD },
	{ "bctg", 0x46, INSTR_RXY_RRRD },
	{ "sty", 0x50, INSTR_RXY_RRRD },
	{ "msy", 0x51, INSTR_RXY_RRRD },
	{ "ny", 0x54, INSTR_RXY_RRRD },
	{ "cly", 0x55, INSTR_RXY_RRRD },
	{ "oy", 0x56, INSTR_RXY_RRRD },
	{ "xy", 0x57, INSTR_RXY_RRRD },
	{ "ly", 0x58, INSTR_RXY_RRRD },
	{ "cy", 0x59, INSTR_RXY_RRRD },
	{ "ay", 0x5a, INSTR_RXY_RRRD },
	{ "sy", 0x5b, INSTR_RXY_RRRD },
	{ "aly", 0x5e, INSTR_RXY_RRRD },
	{ "sly", 0x5f, INSTR_RXY_RRRD },
	{ "sthy", 0x70, INSTR_RXY_RRRD },
	{ "lay", 0x71, INSTR_RXY_RRRD },
	{ "stcy", 0x72, INSTR_RXY_RRRD },
	{ "icy", 0x73, INSTR_RXY_RRRD },
	{ "lb", 0x76, INSTR_RXY_RRRD },
	{ "lgb", 0x77, INSTR_RXY_RRRD },
	{ "lhy", 0x78, INSTR_RXY_RRRD },
	{ "chy", 0x79, INSTR_RXY_RRRD },
	{ "ahy", 0x7a, INSTR_RXY_RRRD },
	{ "shy", 0x7b, INSTR_RXY_RRRD },
	{ "ng", 0x80, INSTR_RXY_RRRD },
	{ "og", 0x81, INSTR_RXY_RRRD },
	{ "xg", 0x82, INSTR_RXY_RRRD },
	{ "mlg", 0x86, INSTR_RXY_RRRD },
	{ "dlg", 0x87, INSTR_RXY_RRRD },
	{ "alcg", 0x88, INSTR_RXY_RRRD },
	{ "slbg", 0x89, INSTR_RXY_RRRD },
	{ "stpq", 0x8e, INSTR_RXY_RRRD },
	{ "lpq", 0x8f, INSTR_RXY_RRRD },
	{ "llgc", 0x90, INSTR_RXY_RRRD },
	{ "llgh", 0x91, INSTR_RXY_RRRD },
	{ "llc", 0x94, INSTR_RXY_RRRD },
	{ "llh", 0x95, INSTR_RXY_RRRD },
	{ "cgh", 0x34, INSTR_RXY_RRRD },
	{ "laey", 0x75, INSTR_RXY_RRRD },
	{ "ltgf", 0x32, INSTR_RXY_RRRD },
	{ "mfy", 0x5c, INSTR_RXY_RRRD },
	{ "mhy", 0x7c, INSTR_RXY_RRRD },
	{ "pfd", 0x36, INSTR_RXY_URRD },
	{ "lrv", 0x1e, INSTR_RXY_RRRD },
	{ "lrvh", 0x1f, INSTR_RXY_RRRD },
	{ "strv", 0x3e, INSTR_RXY_RRRD },
	{ "ml", 0x96, INSTR_RXY_RRRD },
	{ "dl", 0x97, INSTR_RXY_RRRD },
	{ "alc", 0x98, INSTR_RXY_RRRD },
	{ "slb", 0x99, INSTR_RXY_RRRD },
	{ "", 0, INSTR_INVALID }
}

local opcode_e5 = {
	{ "strag", 0x02, INSTR_SSE_RDRD },
	{ "chhsi", 0x54, INSTR_SIL_RDI },
	{ "chsi", 0x5c, INSTR_SIL_RDI },
	{ "cghsi", 0x58, INSTR_SIL_RDI },
	{ "clhhsi", 0x55, INSTR_SIL_RDU },
	{ "clfhsi", 0x5d, INSTR_SIL_RDU },
	{ "clghsi", 0x59, INSTR_SIL_RDU },
	{ "mvhhi", 0x44, INSTR_SIL_RDI },
	{ "mvhi", 0x4c, INSTR_SIL_RDI },
	{ "mvghi", 0x48, INSTR_SIL_RDI },
	{ "lasp", 0x00, INSTR_SSE_RDRD },
	{ "tprot", 0x01, INSTR_SSE_RDRD },
	{ "mvcsk", 0x0e, INSTR_SSE_RDRD },
	{ "mvcdk", 0x0f, INSTR_SSE_RDRD },
	{ "", 0, INSTR_INVALID }
}

local opcode_eb = {
	{ "lmg", 0x04, INSTR_RSY_RRRD },
	{ "srag", 0x0a, INSTR_RSY_RRRD },
	{ "slag", 0x0b, INSTR_RSY_RRRD },
	{ "srlg", 0x0c, INSTR_RSY_RRRD },
	{ "sllg", 0x0d, INSTR_RSY_RRRD },
	{ "tracg", 0x0f, INSTR_RSY_RRRD },
	{ "csy", 0x14, INSTR_RSY_RRRD },
	{ "rllg", 0x1c, INSTR_RSY_RRRD },
	{ "clmh", 0x20, INSTR_RSY_RURD },
	{ "clmy", 0x21, INSTR_RSY_RURD },
	{ "stmg", 0x24, INSTR_RSY_RRRD },
	{ "stctg", 0x25, INSTR_RSY_CCRD },
	{ "stmh", 0x26, INSTR_RSY_RRRD },
	{ "stcmh", 0x2c, INSTR_RSY_RURD },
	{ "stcmy", 0x2d, INSTR_RSY_RURD },
	{ "lctlg", 0x2f, INSTR_RSY_CCRD },
	{ "csg", 0x30, INSTR_RSY_RRRD },
	{ "cdsy", 0x31, INSTR_RSY_RRRD },
	{ "cdsg", 0x3e, INSTR_RSY_RRRD },
	{ "bxhg", 0x44, INSTR_RSY_RRRD },
	{ "bxleg", 0x45, INSTR_RSY_RRRD },
	{ "tmy", 0x51, INSTR_SIY_URD },
	{ "mviy", 0x52, INSTR_SIY_URD },
	{ "niy", 0x54, INSTR_SIY_URD },
	{ "cliy", 0x55, INSTR_SIY_URD },
	{ "oiy", 0x56, INSTR_SIY_URD },
	{ "xiy", 0x57, INSTR_SIY_URD },
	{ "icmh", 0x80, INSTR_RSE_RURD },
	{ "icmh", 0x80, INSTR_RSY_RURD },
	{ "icmy", 0x81, INSTR_RSY_RURD },
	{ "clclu", 0x8f, INSTR_RSY_RRRD },
	{ "stmy", 0x90, INSTR_RSY_RRRD },
	{ "lmh", 0x96, INSTR_RSY_RRRD },
	{ "lmy", 0x98, INSTR_RSY_RRRD },
	{ "lamy", 0x9a, INSTR_RSY_AARD },
	{ "stamy", 0x9b, INSTR_RSY_AARD },
	{ "asi", 0x6a, INSTR_SIY_IRD },
	{ "agsi", 0x7a, INSTR_SIY_IRD },
	{ "alsi", 0x6e, INSTR_SIY_IRD },
	{ "algsi", 0x7e, INSTR_SIY_IRD },
	{ "ecag", 0x4c, INSTR_RSY_RRRD },
	{ "rll", 0x1d, INSTR_RSY_RRRD },
	{ "mvclu", 0x8e, INSTR_RSY_RRRD },
	{ "tp", 0xc0, INSTR_RSL_R0RD },
	{ "", 0, INSTR_INVALID }
}

local opcode_ec = {
	{ "brxhg", 0x44, INSTR_RIE_RRP },
	{ "brxlg", 0x45, INSTR_RIE_RRP },
	{ "crb", 0xf6, INSTR_RRS_RRRDU },
	{ "cgrb", 0xe4, INSTR_RRS_RRRDU },
	{ "crj", 0x76, INSTR_RIE_RRPU },
	{ "cgrj", 0x64, INSTR_RIE_RRPU },
	{ "cib", 0xfe, INSTR_RIS_RURDI },
	{ "cgib", 0xfc, INSTR_RIS_RURDI },
	{ "cij", 0x7e, INSTR_RIE_RUPI },
	{ "cgij", 0x7c, INSTR_RIE_RUPI },
	{ "cit", 0x72, INSTR_RIE_R0IU },
	{ "cgit", 0x70, INSTR_RIE_R0IU },
	{ "clrb", 0xf7, INSTR_RRS_RRRDU },
	{ "clgrb", 0xe5, INSTR_RRS_RRRDU },
	{ "clrj", 0x77, INSTR_RIE_RRPU },
	{ "clgrj", 0x65, INSTR_RIE_RRPU },
	{ "clib", 0xff, INSTR_RIS_RURDU },
	{ "clgib", 0xfd, INSTR_RIS_RURDU },
	{ "clij", 0x7f, INSTR_RIE_RUPU },
	{ "clgij", 0x7d, INSTR_RIE_RUPU },
	{ "clfit", 0x73, INSTR_RIE_R0UU },
	{ "clgit", 0x71, INSTR_RIE_R0UU },
	{ "rnsbg", 0x54, INSTR_RIE_RRUUU },
	{ "rxsbg", 0x57, INSTR_RIE_RRUUU },
	{ "rosbg", 0x56, INSTR_RIE_RRUUU },
	{ "risbg", 0x55, INSTR_RIE_RRUUU },
	{ "", 0, INSTR_INVALID }
}

local opcode_ed[] = {
	{ "mayl", 0x38, INSTR_RXF_FRRDF },
	{ "myl", 0x39, INSTR_RXF_FRRDF },
	{ "may", 0x3a, INSTR_RXF_FRRDF },
	{ "my", 0x3b, INSTR_RXF_FRRDF },
	{ "mayh", 0x3c, INSTR_RXF_FRRDF },
	{ "myh", 0x3d, INSTR_RXF_FRRDF },
	{ "ley", 0x64, INSTR_RXY_FRRD },
	{ "ldy", 0x65, INSTR_RXY_FRRD },
	{ "stey", 0x66, INSTR_RXY_FRRD },
	{ "stdy", 0x67, INSTR_RXY_FRRD },
	{ "sldt", 0x40, INSTR_RXF_FRRDF },
	{ "slxt", 0x48, INSTR_RXF_FRRDF },
	{ "srdt", 0x41, INSTR_RXF_FRRDF },
	{ "srxt", 0x49, INSTR_RXF_FRRDF },
	{ "tdcet", 0x50, INSTR_RXE_FRRD },
	{ "tdcdt", 0x54, INSTR_RXE_FRRD },
	{ "tdcxt", 0x58, INSTR_RXE_FRRD },
	{ "tdget", 0x51, INSTR_RXE_FRRD },
	{ "tdgdt", 0x55, INSTR_RXE_FRRD },
	{ "tdgxt", 0x59, INSTR_RXE_FRRD },
	{ "ldeb", 0x04, INSTR_RXE_FRRD },
	{ "lxdb", 0x05, INSTR_RXE_FRRD },
	{ "lxeb", 0x06, INSTR_RXE_FRRD },
	{ "mxdb", 0x07, INSTR_RXE_FRRD },
	{ "keb", 0x08, INSTR_RXE_FRRD },
	{ "ceb", 0x09, INSTR_RXE_FRRD },
	{ "aeb", 0x0a, INSTR_RXE_FRRD },
	{ "seb", 0x0b, INSTR_RXE_FRRD },
	{ "mdeb", 0x0c, INSTR_RXE_FRRD },
	{ "deb", 0x0d, INSTR_RXE_FRRD },
	{ "maeb", 0x0e, INSTR_RXF_FRRDF },
	{ "mseb", 0x0f, INSTR_RXF_FRRDF },
	{ "tceb", 0x10, INSTR_RXE_FRRD },
	{ "tcdb", 0x11, INSTR_RXE_FRRD },
	{ "tcxb", 0x12, INSTR_RXE_FRRD },
	{ "sqeb", 0x14, INSTR_RXE_FRRD },
	{ "sqdb", 0x15, INSTR_RXE_FRRD },
	{ "meeb", 0x17, INSTR_RXE_FRRD },
	{ "kdb", 0x18, INSTR_RXE_FRRD },
	{ "cdb", 0x19, INSTR_RXE_FRRD },
	{ "adb", 0x1a, INSTR_RXE_FRRD },
	{ "sdb", 0x1b, INSTR_RXE_FRRD },
	{ "mdb", 0x1c, INSTR_RXE_FRRD },
	{ "ddb", 0x1d, INSTR_RXE_FRRD },
	{ "madb", 0x1e, INSTR_RXF_FRRDF },
	{ "msdb", 0x1f, INSTR_RXF_FRRDF },
	{ "lde", 0x24, INSTR_RXE_FRRD },
	{ "lxd", 0x25, INSTR_RXE_FRRD },
	{ "lxe", 0x26, INSTR_RXE_FRRD },
	{ "mae", 0x2e, INSTR_RXF_FRRDF },
	{ "mse", 0x2f, INSTR_RXF_FRRDF },
	{ "sqe", 0x34, INSTR_RXE_FRRD },
	{ "sqd", 0x35, INSTR_RXE_FRRD },
	{ "mee", 0x37, INSTR_RXE_FRRD },
	{ "mad", 0x3e, INSTR_RXF_FRRDF },
	{ "msd", 0x3f, INSTR_RXF_FRRDF },
	{ "", 0, INSTR_INVALID }
}

-- Extracts an operand value from an instruction.
local function extract_operand(code, operand)
    code += operand[2] / 8;
    bits = band(operand[2], 7) + operand[1]
    val = 0
    repeat
        val = lshift(val, 8)
        val = bor(val, *code++)
        bits -= 8
    until(bits > 0)

    val = rshift(val, -bits)
    val = band(val, lshift(lshift(1U,operand[1] - 1), 1) - 1)
    
    -- Check for special long displacement case.
    if(operand[1] == 20 && operand[2] == 20) then
        val = bor(lshift(band(val, 0xff), 12), rshift(band(val, 0xfff00), 8))
    end

    -- Sign extend value if the operand is signed or pc relative.
    if(band(operand->flags, bor(OPERAND_SIGNED, OPERAND_PCREL)) && band(val, lshift(1U,(operand[1] - 1)))) then
        val = bor(val, lshift(lshift(-1U, (operand[1] - 1)), 1))
    end

    -- Double value if the operand is pc relative.
    if(band(operand[2], OPERAND_PCREL)) then
        val = lshift(val, 1)
    end

    -- Length x in an instructions has real length x + 1.
    if(band(operand[2], OPERAND_LENGTH)) then
        val++
    end
    return val
end

local function insn_length(code)
    return lshift((rshift((tonumber(code) + 64), 7) + 1), 1);
end

local find_insn(code){
    opfrag = code[1]
    table = opcode

    if(code[0] == 0x01) then
		table = opcode_01
    elseif(code[0] == 0xa5)
		table = opcode_a5
    elseif(code[0] == 0xa7)
		table = opcode_a7
    elseif(code[0] == 0xb2)
		table = opcode_b2
    elseif(code[0] == 0xb3)
		table = opcode_b3
    elseif(code[0] == 0xb9)
		table = opcode_b9
    elseif(code[0] == 0xc0)
		table = opcode_c0
    elseif(code[0] == 0xc2)
		table = opcode_c2
    elseif(code[0] == 0xc4)
		table = opcode_c4
    elseif(code[0] == 0xc6)
		table = opcode_c6
    elseif(code[0] == 0xc8)
		table = opcode_c8
    elseif(code[0] == 0xe3)
		table = opcode_e3
		opfrag = code[5]
    elseif(code[0] == 0xe5)
		table = opcode_e5
    elseif(code[0] == 0xeb)
		table = opcode_eb
		opfrag = code[5]
    elseif(code[0] == 0xec)
		table = opcode_ec
		opfrag = code[5]
    elseif(code[0] == 0xed)
		table = opcode_ed
		opfrag = code[5]
    else
        opfrag = code[0]
    end

    for k, insn in pairs(table) do
        opmask = formats[insn[3]][1]
        if(insn[2] == band(opfrag, opmask)) then
            return insn
        end
    end
    return NULL
}

------------------------------------------------------------------------------

-- Output a nicely formatted line with an opcode and operands.
local function putop(ctx, text, operands)
    local pos = ctx.pos
    local extra = ""
    if ctx.rel then
      local sym = ctx.symtab[ctx.rel]
      if sym then
        extra = "\t->"..sym
      elseif band(ctx.op, 0x0e000000) ~= 0x0a000000 then
        extra = "\t; 0x"..tohex(ctx.rel)
      end
    end
    if ctx.hexdump > 0 then
      ctx.out(format("%08x  %s  %-5s %s%s\n",
          ctx.addr+pos, tohex(ctx.op), text, concat(operands, ", "), extra))
    else
      ctx.out(format("%08x  %-5s %s%s\n",
          ctx.addr+pos, text, concat(operands, ", "), extra))
    end
    ctx.pos = pos + 4
  end
  
  -- Fallback for unknown opcodes.
  local function unknown(ctx)
    return putop(ctx, ".long", { "0x"..tohex(ctx.op) })
  end
  
  -- Format operand 2 of load/store opcodes.
  local function fmtload(ctx, op, pos)
    local base = map_gpr[band(rshift(op, 16), 15)]
    local x, ofs
    local ext = (band(op, 0x04000000) == 0)
    if not ext and band(op, 0x02000000) == 0 then
      ofs = band(op, 4095)
      if band(op, 0x00800000) == 0 then ofs = -ofs end
      if base == "pc" then ctx.rel = ctx.addr + pos + 8 + ofs end
      ofs = "#"..ofs
    elseif ext and band(op, 0x00400000) ~= 0 then
      ofs = band(op, 15) + band(rshift(op, 4), 0xf0)
      if band(op, 0x00800000) == 0 then ofs = -ofs end
      if base == "pc" then ctx.rel = ctx.addr + pos + 8 + ofs end
      ofs = "#"..ofs
    else
      ofs = map_gpr[band(op, 15)]
      if ext or band(op, 0xfe0) == 0 then
      elseif band(op, 0xfe0) == 0x60 then
        ofs = format("%s, rrx", ofs)
      else
        local sh = band(rshift(op, 7), 31)
        if sh == 0 then sh = 32 end
        ofs = format("%s, %s #%d", ofs, map_shift[band(rshift(op, 5), 3)], sh)
      end
      if band(op, 0x00800000) == 0 then ofs = "-"..ofs end
    end
    if ofs == "#0" then
      x = format("[%s]", base)
    elseif band(op, 0x01000000) == 0 then
      x = format("[%s], %s", base, ofs)
    else
      x = format("[%s, %s]", base, ofs)
    end
    if band(op, 0x01200000) == 0x01200000 then x = x.."!" end
    return x
  end
  
  -- Format operand 2 of vector load/store opcodes.
  local function fmtvload(ctx, op, pos)
    local base = map_gpr[band(rshift(op, 16), 15)]
    local ofs = band(op, 255)*4
    if band(op, 0x00800000) == 0 then ofs = -ofs end
    if base == "pc" then ctx.rel = ctx.addr + pos + 8 + ofs end
    if ofs == 0 then
      return format("[%s]", base)
    else
      return format("[%s, #%d]", base, ofs)
    end
  end
  
  local function fmtvr(op, vr, sh0, sh1)
    if vr == "s" then
      return format("s%d", 2*band(rshift(op, sh0), 15)+band(rshift(op, sh1), 1))
    else
      return format("d%d", band(rshift(op, sh0), 15)+band(rshift(op, sh1-4), 16))
    end
  end
  
  -- Disassemble a single instruction.
  local function disass_ins(ctx)
    local pos = ctx.pos
    local b0, b1, b2, b3 = byte(ctx.code, pos+1, pos+4)
    local op = bor(lshift(b3, 24), lshift(b2, 16), lshift(b1, 8), b0)
    local operands = {}
    local suffix = ""
    local last, name, pat
    local vr
    ctx.op = op
    ctx.rel = nil

    print("noice")
  
    -- local cond = rshift(op, 28)
    -- local opat
    -- if cond == 15 then
    --   opat = map_uncondins[band(rshift(op, 25), 7)]
    -- else
    --   if cond ~= 14 then suffix = map_cond[cond] end
    --   opat = map_condins[band(rshift(op, 25), 7)]
    -- end
    -- while type(opat) ~= "string" do
    --   if not opat then return unknown(ctx) end
    --   opat = opat[band(rshift(op, opat.shift), opat.mask)] or opat._
    -- end
    -- name, pat = match(opat, "^([a-z0-9]*)(.*)")
    -- if sub(pat, 1, 1) == "." then
    --   local s2, p2 = match(pat, "^([a-z0-9.]*)(.*)")
    --   suffix = suffix..s2
    --   pat = p2
    -- end
  
    -- for p in gmatch(pat, ".") do
    --   local x = nil
    --   if p == "D" then
    --     x = map_gpr[band(rshift(op, 12), 15)]
    --   elseif p == "N" then
    --     x = map_gpr[band(rshift(op, 16), 15)]
    --   elseif p == "S" then
    --     x = map_gpr[band(rshift(op, 8), 15)]
    --   elseif p == "M" then
    --     x = map_gpr[band(op, 15)]
    --   elseif p == "d" then
    --     x = fmtvr(op, vr, 12, 22)
    --   elseif p == "n" then
    --     x = fmtvr(op, vr, 16, 7)
    --   elseif p == "m" then
    --     x = fmtvr(op, vr, 0, 5)
    --   elseif p == "P" then
    --     if band(op, 0x02000000) ~= 0 then
    --   x = ror(band(op, 255), 2*band(rshift(op, 8), 15))
    --     else
    --   x = map_gpr[band(op, 15)]
    --   if band(op, 0xff0) ~= 0 then
    --     operands[#operands+1] = x
    --     local s = map_shift[band(rshift(op, 5), 3)]
    --     local r = nil
    --     if band(op, 0xf90) == 0 then
    --       if s == "ror" then s = "rrx" else r = "#32" end
    --     elseif band(op, 0x10) == 0 then
    --       r = "#"..band(rshift(op, 7), 31)
    --     else
    --       r = map_gpr[band(rshift(op, 8), 15)]
    --     end
    --     if name == "mov" then name = s; x = r
    --     elseif r then x = format("%s %s", s, r)
    --     else x = s end
    --   end
    --     end
    --   elseif p == "L" then
    --     x = fmtload(ctx, op, pos)
    --   elseif p == "l" then
    --     x = fmtvload(ctx, op, pos)
    --   elseif p == "B" then
    --     local addr = ctx.addr + pos + 8 + arshift(lshift(op, 8), 6)
    --     if cond == 15 then addr = addr + band(rshift(op, 23), 2) end
    --     ctx.rel = addr
    --     x = "0x"..tohex(addr)
    --   elseif p == "F" then
    --     vr = "s"
    --   elseif p == "G" then
    --     vr = "d"
    --   elseif p == "." then
    --     suffix = suffix..(vr == "s" and ".f32" or ".f64")
    --   elseif p == "R" then
    --     if band(op, 0x00200000) ~= 0 and #operands == 1 then
    --   operands[1] = operands[1].."!"
    --     end
    --     local t = {}
    --     for i=0,15 do
    --   if band(rshift(op, i), 1) == 1 then t[#t+1] = map_gpr[i] end
    --     end
    --     x = "{"..concat(t, ", ").."}"
    --   elseif p == "r" then
    --     if band(op, 0x00200000) ~= 0 and #operands == 2 then
    --   operands[1] = operands[1].."!"
    --     end
    --     local s = tonumber(sub(last, 2))
    --     local n = band(op, 255)
    --     if vr == "d" then n = rshift(n, 1) end
    --     operands[#operands] = format("{%s-%s%d}", last, vr, s+n-1)
    --   elseif p == "W" then
    --     x = band(op, 0x0fff) + band(rshift(op, 4), 0xf000)
    --   elseif p == "T" then
    --     x = "#0x"..tohex(band(op, 0x00ffffff), 6)
    --   elseif p == "U" then
    --     x = band(rshift(op, 7), 31)
    --     if x == 0 then x = nil end
    --   elseif p == "u" then
    --     x = band(rshift(op, 7), 31)
    --     if band(op, 0x40) == 0 then
    --   if x == 0 then x = nil else x = "lsl #"..x end
    --     else
    --   if x == 0 then x = "asr #32" else x = "asr #"..x end
    --     end
    --   elseif p == "v" then
    --     x = band(rshift(op, 7), 31)
    --   elseif p == "w" then
    --     x = band(rshift(op, 16), 31)
    --   elseif p == "x" then
    --     x = band(rshift(op, 16), 31) + 1
    --   elseif p == "X" then
    --     x = band(rshift(op, 16), 31) - last + 1
    --   elseif p == "Y" then
    --     x = band(rshift(op, 12), 0xf0) + band(op, 0x0f)
    --   elseif p == "K" then
    --     x = "#0x"..tohex(band(rshift(op, 4), 0x0000fff0) + band(op, 15), 4)
    --   elseif p == "s" then
    --     if band(op, 0x00100000) ~= 0 then suffix = "s"..suffix end
    --   else
    --     assert(false)
    --   end
    --   if x then
    --     last = x
    --     if type(x) == "number" then x = "#"..x end
    --     operands[#operands+1] = x
    --   end
    -- end
  
    -- return putop(ctx, name..suffix, operands)
  end
  
  ------------------------------------------------------------------------------
  
  -- Disassemble a block of code.
  local function disass_block(ctx, ofs, len)
    if not ofs then ofs = 0 end
    local stop = len and ofs+len or #ctx.code
    ctx.pos = ofs
    ctx.rel = nil
    while ctx.pos < stop do disass_ins(ctx) end
  end
  
  -- Extended API: create a disassembler context. Then call ctx:disass(ofs, len).
  local function create(code, addr, out)
    local ctx = {}
    ctx.code = code
    ctx.addr = addr or 0
    ctx.out = out or io.write
    ctx.symtab = {}
    ctx.disass = disass_block
    ctx.hexdump = 8
    return ctx
  end
  
  -- Simple API: disassemble code (a string) at address and output via out.
  local function disass(code, addr, out)
    create(code, addr, out):disass()
  end
  
  -- Return register name for RID.
  local function regname(r)
    if r < 16 then return map_gpr[r] end
    return "d"..(r-16)
  end
  
  -- Public module functions.
  return {
    create = create,
    disass = disass,
    regname = regname
  }
