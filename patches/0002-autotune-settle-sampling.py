#!/usr/bin/env python3
"""Stop paying for the autotuner's per-render-pass pixel counter once settled.

In the default (bandwidth) algorithm every render pass emits GPU commands that
read a samples-passed counter before and after the pass, and the CPU later
processes the result. After the average for a render pass has settled that work
buys nothing, so we skip it, except for one use in RESAMPLE_EVERY so the
estimate still follows scene changes.

Tuning values come from AUTOTUNE_SETTLE_UPDATES and AUTOTUNE_RESAMPLE_EVERY in
config.env.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _edit import Edits, env_int

SETTLE = env_int("AUTOTUNE_SETTLE_UPDATES", 24, 4, 1000)
RESAMPLE = env_int("AUTOTUNE_RESAMPLE_EVERY", 64, 2, 100000)
F = "src/freedreno/vulkan/tu_autotune.cc"
ed = Edits()

ed.replace(F,
    '   constexpr bool disable(mod_flag f)\n   {',
    '''   constexpr void clear_metric(metric_flag f)
   {
      metric_flags &= ~(uint8_t) f;
   }

   constexpr bool disable(mod_flag f)
   {''',
    "add config_t::clear_metric")

ed.replace(F,
    '''    private:
      exponential_average<uint32_t> mean_samples_passed;

    public:
      void update(uint32_t samples)
      {
         mean_samples_passed.add(samples);
      }
''',
    '''    private:
      exponential_average<uint32_t> mean_samples_passed;
      std::atomic<uint32_t> updates {0};
      std::atomic<uint32_t> uses {0};
      static constexpr uint32_t SETTLE_UPDATES = %d, RESAMPLE_EVERY = %d;

    public:
      void update(uint32_t samples)
      {
         mean_samples_passed.add(samples);
         updates.fetch_add(1, std::memory_order_relaxed);
      }

      /* Crane's Turnip: once enough samples were averaged, skip the samples-passed
       * counter for most uses of this render pass (but keep re-measuring now and then). */
      bool can_skip_sampling()
      {
         if (updates.load(std::memory_order_relaxed) < SETTLE_UPDATES)
            return false;
         return (uses.fetch_add(1, std::memory_order_relaxed) %% RESAMPLE_EVERY) != 0;
      }
''' % (SETTLE, RESAMPLE),
    "add settle tracking to bandwidth algorithm")

ed.replace(F,
    '   *rp_ctx = cb_ctx.attach_rp_entry(device, history, config, rp_state->drawcall_count);',
    '''   if (config.is_enabled(algorithm::BANDWIDTH) && !config.test(mod_flag::PREEMPT_OPTIMIZE) &&
       history.bandwidth.can_skip_sampling())
      config.clear_metric(metric_flag::SAMPLES);

   *rp_ctx = cb_ctx.attach_rp_entry(device, history, config, rp_state->drawcall_count);''',
    "skip samples metric for settled render passes")

ed.commit()
