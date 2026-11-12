#!/usr/bin/env python3
"""OPTIONAL, EXPERIMENTAL: ask the kernel to hold the GPU near X% of max clock.

Off unless the environment variable TU_KGSL_PWR_PERC is set to 2..100, e.g.
TU_KGSL_PWR_PERC=70. When set, the KGSL draw context is created with the
power-constraint flag and a PWRLEVEL constraint of that percentage is requested
for it. The kernel is free to ignore or reject it (many vendor kernels do for
untrusted apps); failures are silent unless TU_DEBUG=startup is set.

Caveat: this pins a clock target, so a value that is too low costs FPS. It is
meant for A/B testing a power cap, not as a default. Not verified on hardware.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _edit import Edits

F = "src/freedreno/vulkan/tu_knl_kgsl.cc"
ed = Edits()

ed.replace(F,
    '''   int ret = safe_ioctl(dev->physical_device->local_fd, IOCTL_KGSL_DRAWCTXT_CREATE, &req);
   if (ret)
      return ret;

   queue->msm_queue_id = req.drawctxt_id;
''',
    '''   /* Crane's Turnip: optional GPU clock hint, enable with TU_KGSL_PWR_PERC=<2..100> */
   static const long pwr_perc = debug_get_num_option("TU_KGSL_PWR_PERC", 0);
   const bool want_pwr = pwr_perc >= KGSL_CONSTRAINT_PWR_PERC_MIN &&
                         pwr_perc <= KGSL_CONSTRAINT_PWR_PERC_MAX;
   if (want_pwr)
      req.flags |= KGSL_CONTEXT_PWR_CONSTRAINT;

   int ret = safe_ioctl(dev->physical_device->local_fd, IOCTL_KGSL_DRAWCTXT_CREATE, &req);
   if (ret && want_pwr) {
      /* Kernel rejected the flag: fall back to a plain context. */
      req.flags &= ~KGSL_CONTEXT_PWR_CONSTRAINT;
      ret = safe_ioctl(dev->physical_device->local_fd, IOCTL_KGSL_DRAWCTXT_CREATE, &req);
   }
   if (ret)
      return ret;

   queue->msm_queue_id = req.drawctxt_id;

   if (want_pwr && (req.flags & KGSL_CONTEXT_PWR_CONSTRAINT)) {
      struct kgsl_device_constraint_pwrlevel pwr = {
         .level = (unsigned int) pwr_perc,
      };
      struct kgsl_device_constraint constraint = {
         .type = KGSL_CONSTRAINT_PWRLEVEL,
         .context_id = req.drawctxt_id,
         .data = &pwr,
         .size = sizeof(pwr),
      };
      struct kgsl_device_getproperty prop = {
         .type = KGSL_PROP_PWR_CONSTRAINT,
         .value = &constraint,
         .sizebytes = sizeof(constraint),
      };
      int pret = safe_ioctl(dev->physical_device->local_fd, IOCTL_KGSL_SETPROPERTY, &prop);
      if (TU_DEBUG(STARTUP))
         mesa_logi("kgsl: GPU clock hint %ld%% %s", pwr_perc,
                   pret ? "rejected by kernel" : "requested");
   }
''',
    "add optional KGSL power constraint")

ed.commit()
