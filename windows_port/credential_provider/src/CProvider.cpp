#include "CProvider.h"
#include "CCredential.h"

CProvider::CProvider() : m_cRef(1), m_cpus(CPUS_INVALID) {
    DllAddRef();
}

CProvider::~CProvider() {
    DllRelease();
}

IFACEMETHODIMP CProvider::QueryInterface(REFIID riid, void** ppv) {
    static const QITAB qit[] = {
        QITABENT(CProvider, ICredentialProvider),
        { 0 },
    };
    return QISearch(this, qit, riid, ppv);
}

IFACEMETHODIMP_(ULONG) CProvider::AddRef() {
    return InterlockedIncrement(&m_cRef);
}

IFACEMETHODIMP_(ULONG) CProvider::Release() {
    long cRef = InterlockedDecrement(&m_cRef);
    if (!cRef) delete this;
    return cRef;
}

IFACEMETHODIMP CProvider::SetUsageScenario(CREDENTIAL_PROVIDER_USAGE_SCENARIO cpus, DWORD dwFlags) {
    // Only support logon and unlock scenarios
    if (cpus == CPUS_LOGON || cpus == CPUS_UNLOCK_WORKSTATION) {
        m_cpus = cpus;
        return S_OK;
    }
    return E_NOTIMPL;
}

IFACEMETHODIMP CProvider::SetSerialization(const CREDENTIAL_PROVIDER_CREDENTIAL_SERIALIZATION* pcpcs) {
    return E_NOTIMPL;
}

IFACEMETHODIMP CProvider::Advise(ICredentialProviderEvents* pcpe, UINT_PTR upAdviseContext) {
    return S_OK; // Simplified
}

IFACEMETHODIMP CProvider::UnAdvise() {
    return S_OK;
}

IFACEMETHODIMP CProvider::GetFieldDescriptorCount(DWORD* pdwCount) {
    *pdwCount = CCredential::GetFieldCount();
    return S_OK;
}

IFACEMETHODIMP CProvider::GetFieldDescriptorAt(DWORD dwIndex, CREDENTIAL_PROVIDER_FIELD_DESCRIPTOR** ppcpfd) {
    return CCredential::GetFieldDescriptorAt(dwIndex, ppcpfd);
}

IFACEMETHODIMP CProvider::GetCredentialCount(DWORD* pdwCount, DWORD* pdwDefault, BOOL* pbAutoLogonWithDefault) {
    *pdwCount = 1; // 1 Face Unlock Credential
    *pdwDefault = CREDENTIAL_PROVIDER_NO_DEFAULT;
    *pbAutoLogonWithDefault = FALSE;
    return S_OK;
}

IFACEMETHODIMP CProvider::GetCredentialAt(DWORD dwIndex, ICredentialProviderCredential** ppcpc) {
    if (dwIndex != 0) return E_INVALIDARG;
    
    CCredential* pCred = new CCredential();
    if (pCred) {
        HRESULT hr = pCred->QueryInterface(IID_PPV_ARGS(ppcpc));
        pCred->Release();
        return hr;
    }
    return E_OUTOFMEMORY;
}
