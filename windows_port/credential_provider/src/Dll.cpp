#include "common.h"
#include "guid.h"
#include "CProvider.h"

long g_cRef = 0;
HINSTANCE g_hinst = NULL;

void DllAddRef() {
    InterlockedIncrement(&g_cRef);
}

void DllRelease() {
    InterlockedDecrement(&g_cRef);
}

BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved) {
    if (fdwReason == DLL_PROCESS_ATTACH) {
        g_hinst = hinstDLL;
        DisableThreadLibraryCalls(hinstDLL);
    }
    return TRUE;
}

HRESULT WINAPI DllGetClassObject(REFCLSID rclsid, REFIID riid, void** ppv) {
    if (rclsid == CLSID_NovaUnlockProvider) {
        CProvider* pProvider = new CProvider();
        if (pProvider) {
            HRESULT hr = pProvider->QueryInterface(riid, ppv);
            pProvider->Release();
            return hr;
        }
        return E_OUTOFMEMORY;
    }
    return CLASS_E_CLASSNOTAVAILABLE;
}

HRESULT WINAPI DllCanUnloadNow() {
    return g_cRef > 0 ? S_FALSE : S_OK;
}

// Note: Real registration requires setting COM registry keys
// For simplicity, we provide a .reg file instead of implementing DllRegisterServer.
HRESULT WINAPI DllRegisterServer() {
    return S_OK;
}

HRESULT WINAPI DllUnregisterServer() {
    return S_OK;
}
