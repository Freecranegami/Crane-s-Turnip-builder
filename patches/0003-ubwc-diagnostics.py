#!/usr/bin/env python3
"""UBWC diagnostics (no behaviour change).

UBWC is Adreno's framebuffer compression. If swapchain/game render targets end
up uncompressed, memory traffic and power go up. This patch only REPORTS:

  * TU_DEBUG=startup  -> logs the kernel's UBWC version and highest bank bit
  * TU_UBWC_REPORT=1  -> logs every created color/depth attachment image with
                         its size, format, tile mode and whether UBWC is on

Read the output with `adb logcat | grep -i ubwc`. Large render targets that
show ubwc=0 are the ones worth investigating.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _edit import Edits

ed = Edits()

ed.replace("src/freedreno/vulkan/tu_image.cc",
    '''   return VK_SUCCESS;
}
TU_GENX(tu_image_update_layout);''',
    '''   {
      /* Crane's Turnip: optional UBWC report, enable with TU_UBWC_REPORT=1 */
      static const bool ubwc_report = debug_get_bool_option("TU_UBWC_REPORT", false);
      if (unlikely(ubwc_report) &&
          (image->vk.usage & (VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT |
                              VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT))) {
         mesa_logi("ubwc-report: %ux%u fmt=%d samples=%u tile_mode=%d ubwc=%d modifier=0x%llx",
                   image->vk.extent.width, image->vk.extent.height, (int) image->vk.format,
                   (unsigned) image->vk.samples, (int) image->layout[0].tile_mode,
                   (int) image->layout[0].ubwc, (unsigned long long) modifier);
      }
   }

   return VK_SUCCESS;
}
TU_GENX(tu_image_update_layout);''',
    "add TU_UBWC_REPORT image logging")

ed.replace("src/freedreno/vulkan/tu_knl_kgsl.cc",
    '''   uint32_t ubwc_version;
   if (get_kgsl_prop(fd, KGSL_PROP_UBWC_MODE, &ubwc_version,
                     sizeof(ubwc_version)))
      goto fail;
''',
    '''   uint32_t ubwc_version;
   if (get_kgsl_prop(fd, KGSL_PROP_UBWC_MODE, &ubwc_version,
                     sizeof(ubwc_version)))
      goto fail;

   if (TU_DEBUG(STARTUP))
      mesa_logi("kgsl: ubwc_version=%u highest_bank_bit=%u", ubwc_version,
                highest_bank_bit);
''',
    "log KGSL UBWC config at startup")

ed.commit()
