# spectranext_sdk_import.cmake
# CMake module for Spectranext SDK - sets up z88dk toolchain and provides convenience targets

# Skip CMake's compiler test - z88dk toolchain handles compilation
# These must be set before project() is called
if(NOT DEFINED CMAKE_C_COMPILER_WORKS)
    set(CMAKE_C_COMPILER_WORKS TRUE CACHE INTERNAL "C compiler works (z88dk toolchain)")
endif()
if(NOT DEFINED CMAKE_CXX_COMPILER_WORKS)
    set(CMAKE_CXX_COMPILER_WORKS TRUE CACHE INTERNAL "C++ compiler works (z88dk toolchain)")
endif()

# Find and set SPX_SCRIPT and SPX_PYTHON_PATH variables
# These are exported as cache variables for use in custom operations
# Set at module load time so they're always available
if(NOT DEFINED SPX_SCRIPT)
    if(DEFINED ENV{SPECTRANEXT_SDK_PATH})
        # On Windows, use spx.bat which handles venv Python automatically
        # On Unix, use spx.py with Python executable
        if(WIN32)
            set(SPX_SCRIPT "$ENV{SPECTRANEXT_SDK_PATH}/bin/spx.bat" CACHE FILEPATH "Path to spx.bat script")
            # spx.bat handles Python, so we don't need SPX_PYTHON_PATH on Windows
        else()
            set(SPX_SCRIPT "$ENV{SPECTRANEXT_SDK_PATH}/bin/spx.py" CACHE FILEPATH "Path to spx.py script")
            # Use venv Python from SDK (Unix paths)
            if(EXISTS "$ENV{SPECTRANEXT_SDK_PATH}/venv/bin/python3")
                set(SPX_PYTHON_PATH "$ENV{SPECTRANEXT_SDK_PATH}/venv/bin/python3" CACHE FILEPATH "Path to Python executable for SPX tools")
            elseif(EXISTS "$ENV{SPECTRANEXT_SDK_PATH}/venv/bin/python")
                set(SPX_PYTHON_PATH "$ENV{SPECTRANEXT_SDK_PATH}/venv/bin/python" CACHE FILEPATH "Path to Python executable for SPX tools")
            endif()
        endif()
    endif()
    
    # Fallback: try to find Python in PATH if venv not found (Unix only)
    if(NOT WIN32 AND NOT DEFINED SPX_PYTHON_PATH)
        find_program(SPX_PYTHON_PATH
            NAMES python3 python
            DOC "Python executable for SPX tools"
        )
        if(SPX_PYTHON_PATH)
            set(SPX_PYTHON_PATH "${SPX_PYTHON_PATH}" CACHE FILEPATH "Path to Python executable for SPX tools" FORCE)
        endif()
    endif()
endif()

# Set up SPX_EXECUTABLE_COMMAND cache variable
# On Windows: use spx.bat directly, on Unix: use Python + spx.py
if(NOT DEFINED SPX_EXECUTABLE_COMMAND)
    if(DEFINED SPX_SCRIPT)
        if(WIN32)
            set(SPX_EXECUTABLE_COMMAND ${SPX_SCRIPT} CACHE STRING "Command to execute SPX tools (spx.bat on Windows)")
        else()
            if(DEFINED SPX_PYTHON_PATH)
                set(SPX_EXECUTABLE_COMMAND ${SPX_PYTHON_PATH} ${SPX_SCRIPT} CACHE STRING "Command to execute SPX tools (python spx.py on Unix)")
            endif()
        endif()
    endif()
endif()

# Initialize Spectranext SDK
# Sets up toolchain, includes directories, and configures z88dk
function(spectranext_sdk_init)
    # Set up toolchain if SPECTRANEXT_TOOLCHAIN is defined
    if(DEFINED ENV{SPECTRANEXT_TOOLCHAIN} AND NOT DEFINED CMAKE_TOOLCHAIN_FILE)
        set(CMAKE_TOOLCHAIN_FILE "$ENV{SPECTRANEXT_TOOLCHAIN}" CACHE FILEPATH "CMake toolchain file" FORCE)
    endif()
    
    # Set ZCCTARGET if not already set
    if(NOT DEFINED ZCCTARGET)
        if(DEFINED ENV{ZCCTARGET})
            set(ZCCTARGET "$ENV{ZCCTARGET}" CACHE STRING "z88dk target configuration" FORCE)
        else()
            set(ZCCTARGET "zx" CACHE STRING "z88dk target configuration" FORCE)
        endif()
    endif()
    
    # Add Spectranext include directory if available
    if(DEFINED ENV{SPECTRANEXT_INCLUDE_DIR})
        include_directories("$ENV{SPECTRANEXT_INCLUDE_DIR}")
    endif()

    link_directories("$ENV{SPECTRANEXT_SDK_PATH}/clibs")
    
    # Add z88dk include directory
    if(DEFINED ENV{SPECTRANEXT_SDK_PATH})
        set(Z88DK_INCLUDE_DIR "$ENV{SPECTRANEXT_SDK_PATH}/z88dk/include")
        if(EXISTS "${Z88DK_INCLUDE_DIR}")
            include_directories("${Z88DK_INCLUDE_DIR}")
        endif()
    endif()
    
    message(STATUS "Spectranext SDK initialized")
    message(STATUS "  ZCCTARGET: ${ZCCTARGET}")
    if(DEFINED CMAKE_TOOLCHAIN_FILE)
        message(STATUS "  Toolchain: ${CMAKE_TOOLCHAIN_FILE}")
    endif()
endfunction()

# Set boot BASIC program
# Creates boot.bas file, compiles it to boot.zx, and creates upload_boot target
# Usage: spectranext_set_boot("10 PRINT \"Hello\"") or spectranext_set_boot("PRINT \"Hello\"" 20)
function(spectranext_set_boot BOOT_BASIC)
    # Find makebas (Python wrapper)
    if(DEFINED ENV{SPECTRANEXT_SDK_PATH})
        set(ZMAKEBAS_EXECUTABLE "$ENV{SPECTRANEXT_SDK_PATH}/bin/makebas")
    else()
        # Try to find in PATH
        find_program(ZMAKEBAS_EXECUTABLE makebas)
    endif()
    
    if(NOT ZMAKEBAS_EXECUTABLE OR NOT EXISTS "${ZMAKEBAS_EXECUTABLE}")
        message(WARNING "makebas not found, boot file will not be created")
        return()
    endif()
    
    # Use exported SPX variables
    # Try to find them if not already set
    if(NOT DEFINED SPX_SCRIPT)
        if(DEFINED ENV{SPECTRANEXT_SDK_PATH})
            set(SPX_SCRIPT "$ENV{SPECTRANEXT_SDK_PATH}/bin/spx.py" CACHE FILEPATH "Path to spx.py script")
        endif()
    endif()
    
    if(NOT DEFINED SPX_PYTHON_PATH)
        if(DEFINED ENV{SPECTRANEXT_SDK_PATH})
            if(WIN32)
                if(EXISTS "$ENV{SPECTRANEXT_SDK_PATH}/venv/Scripts/python.exe")
                    set(SPX_PYTHON_PATH "$ENV{SPECTRANEXT_SDK_PATH}/venv/Scripts/python.exe" CACHE FILEPATH "")
                endif()
            else()
                if(EXISTS "$ENV{SPECTRANEXT_SDK_PATH}/venv/bin/python3")
                    set(SPX_PYTHON_PATH "$ENV{SPECTRANEXT_SDK_PATH}/venv/bin/python3" CACHE FILEPATH "")
                endif()
            endif()
        endif()
        if(NOT SPX_PYTHON_PATH)
            find_program(SPX_PYTHON_PATH NAMES python3.exe python.exe python3 python)
        endif()
    endif()
    
    if(NOT SPX_SCRIPT OR NOT EXISTS "${SPX_SCRIPT}")
        # Silently skip - boot upload is optional
        return()
    endif()
    
    # Use cached SPX_EXECUTABLE_COMMAND if available, otherwise set it up
    if(NOT DEFINED SPX_EXECUTABLE_COMMAND)
        if(WIN32)
            set(SPX_EXECUTABLE_COMMAND ${SPX_SCRIPT} CACHE STRING "Command to execute SPX tools (spx.bat on Windows)")
        else()
            if(NOT SPX_PYTHON_PATH)
                # Silently skip - boot upload is optional
                return()
            endif()
            set(SPX_EXECUTABLE_COMMAND ${SPX_PYTHON_PATH} ${SPX_SCRIPT} CACHE STRING "Command to execute SPX tools (python spx.py on Unix)")
        endif()
    endif()
    
    # Create boot.bas file in binary directory
    set(BOOT_BAS_FILE "${CMAKE_BINARY_DIR}/boot.bas")
    set(BOOT_ZX_FILE "${CMAKE_BINARY_DIR}/boot.zx")
    
    file(WRITE "${BOOT_BAS_FILE}" "${BOOT_BASIC}\n")
    
    # Compile boot.bas to boot.zx using makebas
    add_custom_command(
        OUTPUT "${BOOT_ZX_FILE}"
        COMMAND ${ZMAKEBAS_EXECUTABLE} -o "${BOOT_ZX_FILE}" -a 10 "${BOOT_BAS_FILE}"
        DEPENDS "${BOOT_BAS_FILE}"
        COMMENT "Compiling boot.bas to boot.zx (starting at line 10)"
    )
    
    # Create a target for the boot file
    add_custom_target(boot_file DEPENDS "${BOOT_ZX_FILE}")
    
    # Create upload_boot target
    set(REMOTE_BOOT_PATH "boot.zx")
    add_custom_target(upload_boot
        COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target boot_file
        COMMAND ${SPX_EXECUTABLE_COMMAND} put ${BOOT_ZX_FILE} ${REMOTE_BOOT_PATH}
        DEPENDS boot_file
        COMMENT "Building and uploading boot.zx"
    )
    
    message(STATUS "Boot BASIC program set (line 10): ${BOOT_BASIC}")
    message(STATUS "  Created target: upload_boot")
endfunction()

# Add extra output targets for a project
# Creates targets: <project_name>_upload, <project_name>_program, <project_name>_autoboot
# Also creates convenience targets: program, upload, autoboot
# Usage: spectranext_add_extra_outputs(my_project)
function(spectranext_add_extra_outputs PROJECT_NAME)
    # Use exported SPX variables - try to find them if not set
    if(NOT DEFINED SPX_SCRIPT)
        if(DEFINED ENV{SPECTRANEXT_SDK_PATH})
            if(WIN32)
                set(SPX_SCRIPT "$ENV{SPECTRANEXT_SDK_PATH}/bin/spx.bat" CACHE FILEPATH "")
            else()
                set(SPX_SCRIPT "$ENV{SPECTRANEXT_SDK_PATH}/bin/spx.py" CACHE FILEPATH "")
            endif()
        endif()
    endif()
    
    if(NOT SPX_SCRIPT OR NOT EXISTS "${SPX_SCRIPT}")
        # Silently skip - upload targets are optional
        return()
    endif()
    
    # Use cached SPX_EXECUTABLE_COMMAND if available, otherwise set it up
    if(NOT DEFINED SPX_EXECUTABLE_COMMAND)
        if(WIN32)
            set(SPX_EXECUTABLE_COMMAND ${SPX_SCRIPT} CACHE STRING "Command to execute SPX tools (spx.bat on Windows)")
        else()
            if(NOT DEFINED SPX_PYTHON_PATH)
                if(DEFINED ENV{SPECTRANEXT_SDK_PATH})
                    if(EXISTS "$ENV{SPECTRANEXT_SDK_PATH}/venv/bin/python3")
                        set(SPX_PYTHON_PATH "$ENV{SPECTRANEXT_SDK_PATH}/venv/bin/python3" CACHE FILEPATH "")
                    endif()
                endif()
                if(NOT SPX_PYTHON_PATH)
                    find_program(SPX_PYTHON_PATH NAMES python3 python)
                endif()
            endif()
            if(NOT SPX_PYTHON_PATH)
                # Silently skip - upload targets are optional
                return()
            endif()
            set(SPX_EXECUTABLE_COMMAND ${SPX_PYTHON_PATH} ${SPX_SCRIPT} CACHE STRING "Command to execute SPX tools (python spx.py on Unix)")
        endif()
    endif()
    
    # Determine binary paths from target properties (.bin and .tap)
    if(TARGET ${PROJECT_NAME})
        get_target_property(OUTPUT_NAME ${PROJECT_NAME} OUTPUT_NAME)
        if(NOT OUTPUT_NAME)
            set(OUTPUT_NAME ${PROJECT_NAME})
        endif()
        
        get_target_property(RUNTIME_OUTPUT_DIRECTORY ${PROJECT_NAME} RUNTIME_OUTPUT_DIRECTORY)
        if(RUNTIME_OUTPUT_DIRECTORY)
            set(BIN_PATH "${RUNTIME_OUTPUT_DIRECTORY}/${OUTPUT_NAME}.bin")
            set(TAP_PATH "${RUNTIME_OUTPUT_DIRECTORY}/${OUTPUT_NAME}.tap")
        else()
            # Use default output directory
            if(CMAKE_RUNTIME_OUTPUT_DIRECTORY)
                set(BIN_PATH "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/${OUTPUT_NAME}.bin")
                set(TAP_PATH "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}/${OUTPUT_NAME}.tap")
            else()
                set(BIN_PATH "${CMAKE_CURRENT_BINARY_DIR}/${OUTPUT_NAME}.bin")
                set(TAP_PATH "${CMAKE_CURRENT_BINARY_DIR}/${OUTPUT_NAME}.tap")
            endif()
        endif()
    else()
        # Target doesn't exist yet, use default paths
        set(BIN_PATH "${CMAKE_CURRENT_BINARY_DIR}/${PROJECT_NAME}.bin")
        set(TAP_PATH "${CMAKE_CURRENT_BINARY_DIR}/${PROJECT_NAME}.tap")
    endif()
    
    # Remote paths
    set(REMOTE_BIN_PATH "${PROJECT_NAME}.bin")
    set(REMOTE_TAP_PATH "${PROJECT_NAME}.tap")

    if(TARGET upload_boot)
        add_custom_target(${PROJECT_NAME}_upload_bin
            COMMAND ${SPX_EXECUTABLE_COMMAND} put ${BIN_PATH} ${REMOTE_BIN_PATH}
            COMMENT "Building and uploading ${PROJECT_NAME}.bin to ${REMOTE_BIN_PATH}"
            DEPENDS ${PROJECT_NAME} upload_boot
        )

        add_custom_target(${PROJECT_NAME}_upload_tap
            COMMAND ${SPX_EXECUTABLE_COMMAND} put ${TAP_PATH} ${REMOTE_TAP_PATH}
            COMMENT "Building and uploading ${PROJECT_NAME}.tap to ${REMOTE_TAP_PATH}"
            DEPENDS ${PROJECT_NAME} upload_boot
        )
    else()
        add_custom_target(${PROJECT_NAME}_upload_bin
            COMMAND ${SPX_EXECUTABLE_COMMAND} put ${BIN_PATH} ${REMOTE_BIN_PATH}
            COMMENT "Building and uploading ${PROJECT_NAME}.bin to ${REMOTE_BIN_PATH}"
            DEPENDS ${PROJECT_NAME}
        )
        add_custom_target(${PROJECT_NAME}_upload_tap
            COMMAND ${SPX_EXECUTABLE_COMMAND} put ${TAP_PATH} ${REMOTE_TAP_PATH}
            COMMENT "Building and uploading ${PROJECT_NAME}.tap to ${REMOTE_TAP_PATH}"
            DEPENDS ${PROJECT_NAME}
        )
    endif()

    add_custom_target(${PROJECT_NAME}_bin_autoboot
        COMMAND ${SPX_EXECUTABLE_COMMAND} autoboot
        COMMENT "Rebooting into .bin (boot.zx)"
        DEPENDS ${PROJECT_NAME}_upload_bin
    )

    add_custom_target(${PROJECT_NAME}_tap_autoboot
        COMMAND ${SPX_EXECUTABLE_COMMAND} autoboot
        COMMENT "Rebooting into .tap (boot.zx)"
        DEPENDS ${PROJECT_NAME}_upload_tap
    )

    message(STATUS "Created targets for ${PROJECT_NAME}:")
    message(STATUS "  ${PROJECT_NAME}_upload_bin - Build and upload .bin file")
    message(STATUS "  ${PROJECT_NAME}_upload_tap - Build and upload .tap file")
    message(STATUS "  ${PROJECT_NAME}_bin_autoboot - Build, upload .bin, and autoboot")
    message(STATUS "  ${PROJECT_NAME}_tap_autoboot - Build, upload .tap, and autoboot")
    if(TARGET upload_boot)
        message(STATUS "  Note: upload_bin and upload_tap depend on upload_boot")
    endif()
endfunction()

