#include <spectranext.h>
#include <stdio.h>

#include "app.h"
#include "ui.h"

int main(void)
{
    printf("[main] start\n");
    if (spectranext_detect() < 1) {
        printf("[main] spectranext_detect failed\n");
        ui_init(NULL, NULL, NULL);
        ui_show_message("Spectranext is required to run this program.\nSee spectranext.net");
        while (1) {
            ui_iteration();
#asm
            halt
#endasm
        }
    }

    if (app_init() != 0) {
        printf("[main] app_init failed\n");
        ui_init(NULL, NULL, NULL);
        ui_show_message("Could not init app, did you occupy volume 2?");
        while (1) {
            ui_iteration();
#asm
            halt
#endasm
        }
    }

    printf("[main] entering main loop\n");
    while (1) {
        app_iteration();
    }
}
