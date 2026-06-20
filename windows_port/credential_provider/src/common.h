#pragma once

#include <windows.h>
#include <credentialprovider.h>
#include <ntsecapi.h>
#include <strsafe.h>

#pragma comment(lib, "secur32.lib")
#pragma comment(lib, "advapi32.lib")
#pragma comment(lib, "shlwapi.lib")

extern long g_cRef;
extern HINSTANCE g_hinst;

void DllAddRef();
void DllRelease();
