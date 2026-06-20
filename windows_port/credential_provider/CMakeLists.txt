cmake_minimum_required(VERSION 3.15)
project(NovaUnlockProvider)

set(CMAKE_CXX_STANDARD 14)

add_library(NovaUnlockProvider SHARED
    src/guid.cpp
    src/Dll.cpp
    src/CProvider.cpp
    src/CCredential.cpp
)

target_link_libraries(NovaUnlockProvider
    secur32
    advapi32
    shlwapi
    credui
)

# Use the DEF file for exports
set_target_properties(NovaUnlockProvider PROPERTIES 
    LINK_FLAGS "/DEF:${CMAKE_CURRENT_SOURCE_DIR}/src/NovaUnlockProvider.def"
)
