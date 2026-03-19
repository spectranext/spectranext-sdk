# libterm printf example

This example links **libterm** so that `printf` output is sent to the Spectranext **terminal stdout** I/O decode (port **`$073B`**). The RP2350 captures those bytes and, when **USB is connected** to a host, **streams them automatically**—you do **not** need to run any device or host command to “fetch” or “enable” logs.

## Prerequisites

- Spectranext SDK installed and sourced (see [SDK Setup](../../../docs/docs/development/sdk) or the main Spectranext docs)
- Build Spectranet libraries (including libterm) and install into the SDK so `libterm` is available in the SDK clibs

## Build

From this directory:

```bash
cmake -B build
cmake --build build
```

Output: `libterm_printf.bin` and `libterm_printf.tap` in the `build` directory.

## Seeing output

1. Transfer and run the program on the Spectrum (Spectranext).
2. **Connect USB** to your PC (e.g. open [device.spectranext.net](https://device.spectranext.net) or use `spx`).
3. `printf` lines from the Z80 appear on the host **as they are captured**—no extra commands required.

See [Logging and terminal stdout](../../../docs/docs/development/logging.mdx) for full details.
