cmake_minimum_required(VERSION 3.16)

# Import Spectranext SDK - MUST be before project()
include($ENV{SPECTRANEXT_SDK_PATH}/cmake/spectranext_sdk_import.cmake)
spectranext_sdk_init()

project(libterm_printf C)

add_executable(libterm_printf main.c)

target_compile_options(libterm_printf PUBLIC -debug)
target_link_libraries(libterm_printf PUBLIC
    -lndos
    -llibterm
    -llibspectranet.lib
)
target_link_options(libterm_printf PUBLIC
    -debug
    -create-app
    -pragma-redirect:fputc_cons=spectranext_fputc_cons
)

# Set boot BASIC program (optional)
spectranext_set_boot("
10 %tapein \"libterm_printf.tap\"
20 LOAD \"\"
")

spectranext_add_extra_outputs(libterm_printf)
