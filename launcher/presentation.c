#include "mod_plugins.h"
#include <string.h>
#include <stdlib.h>

static void activate_view(void) {
    char mode[32] = "wide";
    (void)psx_mod_option_value("ridge.presentation", "view", "mode", mode, sizeof(mode));
    (void)psx_mod_set_fixed_display_aspect(16, 9);
    if (strcmp(mode, "adaptive") == 0)
        (void)psx_mod_set_adaptive_display_aspect(16, 9);
}

static void activate_motion(void) {
    if (getenv("RIDGE_NATIVE_SCENE")) return;
    char target[16] = "0";
    (void)psx_mod_option_value("ridge.presentation", "motion", "target", target, sizeof(target));
    (void)psx_mod_set_frame_interpolation((uint32_t)strtoul(target, NULL, 10));
}

PSX_MOD_CONSTRUCTOR(register_ridge_view) {
    (void)psx_mod_register_activation_plugin("ridge.view", activate_view);
    (void)psx_mod_register_activation_plugin("ridge.motion", activate_motion);
}
