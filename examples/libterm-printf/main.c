/*
 * libterm printf example
 *
 * Links libterm so printf/fputc_cons output goes to the Spectranext terminal stdout
 * port decode ($073B). The RP2350 forwards captured text over USB CDC when a host
 * is connected—no commands are required to observe logs.
 *
 * Build: from sdk/examples/libterm-printf run
 *   cmake -B build && cmake --build build
 * (requires Spectranext SDK sourced; see README)
 */

#include <stdio.h>

int main(void)
{
    printf("Hello from libterm\n");
    printf("Connect USB to your PC to see this on the host (no commands needed).\n");
    return 0;
}
