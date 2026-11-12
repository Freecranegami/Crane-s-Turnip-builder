#!/usr/bin/env python3
"""Bias Turnip's sysmem-vs-GMEM autotuner toward GMEM (tiled rendering).

GMEM keeps framebuffer traffic on-chip; SYSMEM writes everything to DRAM. DRAM
traffic is a large part of GPU power and heat on phones. Stock Turnip picks
SYSMEM whenever its bandwidth estimate says sysmem <= gmem. This patch makes
SYSMEM win only if it is clearly cheaper:

    pick SYSMEM  if  sysmem_bw * BIAS <= gmem_bw * 100

BIAS is a percentage. 100 = stock behaviour. The default comes from
GMEM_BIAS_PCT in config.env and can be overridden per game at run time with
the environment variable TU_AUTOTUNE_GMEM_BIAS (e.g. 100, 125, 150).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _edit import Edits, env_int

BIAS = env_int("GMEM_BIAS_PCT", 125, 100, 400)
F = "src/freedreno/vulkan/tu_autotune.cc"
ed = Edits()

ed.replace(F,
    '#include "util/rand_xor.h"\n',
    '#include "util/rand_xor.h"\n#include "util/u_debug.h"\n',
    "include util/u_debug.h")

ed.replace(F,
    'enum class tu_autotune::algorithm : uint8_t {',
    '''/* Crane's Turnip: how strongly to prefer GMEM over SYSMEM, in percent (100 = stock).
 * Override at run time with TU_AUTOTUNE_GMEM_BIAS. */
static inline uint32_t
at_gmem_bias_pct(void)
{
   static const uint32_t pct = []() {
      long v = debug_get_num_option("TU_AUTOTUNE_GMEM_BIAS", %d);
      if (v < 100)
         v = 100;
      if (v > 400)
         v = 400;
      return (uint32_t) v;
   }();
   return pct;
}

enum class tu_autotune::algorithm : uint8_t {''' % BIAS,
    "add GMEM bias helper")

ed.replace(F,
    '         bool select_sysmem = sysmem_bandwidth <= gmem_bandwidth;',
    '         bool select_sysmem = sysmem_bandwidth * at_gmem_bias_pct() <= gmem_bandwidth * 100;',
    "apply GMEM bias in bandwidth heuristic")

ed.commit()
