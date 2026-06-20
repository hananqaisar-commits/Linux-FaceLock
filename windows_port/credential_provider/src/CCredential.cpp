#include "CCredential.h"
#include <ntsecapi.h>
#include <wincred.h>
#include <Lmcons.h>
#include <Shlwapi.h>

CCredential::CCredential() : m_cRef(1) {
    DllAddRef();
}

CCredential::~CCredential() {
    DllRelease();
}

IFACEMETHODIMP CCredential::QueryInterface(REFIID riid, void** ppv) {
    static const QITAB qit[] = {
        QITABENT(CCredential, ICredentialProviderCredential),
        { 0 },
    };
    return QISearch(this, qit, riid, ppv);
}

IFACEMETHODIMP_(ULONG) CCredential::AddRef() { return InterlockedIncrement(&m_cRef); }
IFACEMETHODIMP_(ULONG) CCredential::Release() { 
    long cRef = InterlockedDecrement(&m_cRef);
    if (!cRef) delete this;
    return cRef;
}

// Minimal stub implementations for basic UI
IFACEMETHODIMP CCredential::Advise(ICredentialProviderCredentialEvents* pcpce) { return S_OK; }
IFACEMETHODIMP CCredential::UnAdvise() { return S_OK; }
IFACEMETHODIMP CCredential::SetSelected(BOOL* pbAutoLogon) { return S_OK; }
IFACEMETHODIMP CCredential::SetDeserializedAuthenticationState(DWORD dwState) { return S_OK; }
IFACEMETHODIMP CCredential::SetDeserializedAuthenticationState(DWORD dwState, CREDENTIAL_PROVIDER_CREDENTIAL_SERIALIZATION* pcpcs) { return S_OK; }

IFACEMETHODIMP CCredential::GetFieldState(DWORD dwIndex, CREDENTIAL_PROVIDER_FIELD_STATE* pcpfs, CREDENTIAL_PROVIDER_FIELD_INTERACTIVE_STATE* pcpfis) {
    *pcpfs = CPFS_DISPLAY_IN_BOTH;
    *pcpfis = CPFIS_NONE;
    return S_OK;
}

IFACEMETHODIMP CCredential::GetStringValue(DWORD dwIndex, LPWSTR* ppsz) {
    if (dwIndex == 0) {
        return SHStrDupW(L"NovaUnlock Face Login", ppsz);
    }
    return E_NOTIMPL;
}

IFACEMETHODIMP CCredential::GetBitmapValue(DWORD dwIndex, HBITMAP* phbmp) { return E_NOTIMPL; }
IFACEMETHODIMP CCredential::GetCheckboxValue(DWORD dwIndex, BOOL* pbChecked, LPWSTR* ppszLabel) { return E_NOTIMPL; }
IFACEMETHODIMP CCredential::GetSubmitButtonValue(DWORD dwIndex, DWORD* pdwAdjacentTo) { return E_NOTIMPL; }
IFACEMETHODIMP CCredential::GetComboBoxValueCount(DWORD dwIndex, DWORD* pcCount, DWORD* pdwDefault) { return E_NOTIMPL; }
IFACEMETHODIMP CCredential::GetComboBoxValueAt(DWORD dwIndex, DWORD dwItem, LPWSTR* ppszItem) { return E_NOTIMPL; }
IFACEMETHODIMP CCredential::SetStringValue(DWORD dwIndex, LPCWSTR psz) { return E_NOTIMPL; }
IFACEMETHODIMP CCredential::SetCheckboxValue(DWORD dwIndex, BOOL bChecked) { return E_NOTIMPL; }
IFACEMETHODIMP CCredential::SetComboBoxSelectedValue(DWORD dwIndex, DWORD dwSelectedItem) { return E_NOTIMPL; }
IFACEMETHODIMP CCredential::CommandLinkClicked(DWORD dwIndex) { return S_OK; }
IFACEMETHODIMP CCredential::ReportResult(NTSTATUS ntsStatus, NTSTATUS ntsSubstatus, LPWSTR* ppszOptionalStatusText, CREDENTIAL_PROVIDER_STATUS_ICON* pcpsiOptionalStatusIcon) { return S_OK; }

HRESULT CCredential::GetFieldDescriptorAt(DWORD dwIndex, CREDENTIAL_PROVIDER_FIELD_DESCRIPTOR** ppcpfd) {
    if (dwIndex == 0) {
        CREDENTIAL_PROVIDER_FIELD_DESCRIPTOR* pcpfd = (CREDENTIAL_PROVIDER_FIELD_DESCRIPTOR*)CoTaskMemAlloc(sizeof(CREDENTIAL_PROVIDER_FIELD_DESCRIPTOR));
        pcpfd->dwFieldID = 0;
        pcpfd->cpft = CPFT_LARGE_TEXT;
        pcpfd->pszLabel = NULL;
        pcpfd->guidFieldType = GUID_NULL;
        *ppcpfd = pcpfd;
        return S_OK;
    } else if (dwIndex == 1) {
        CREDENTIAL_PROVIDER_FIELD_DESCRIPTOR* pcpfd = (CREDENTIAL_PROVIDER_FIELD_DESCRIPTOR*)CoTaskMemAlloc(sizeof(CREDENTIAL_PROVIDER_FIELD_DESCRIPTOR));
        pcpfd->dwFieldID = 1;
        pcpfd->cpft = CPFT_SUBMIT_BUTTON;
        pcpfd->pszLabel = NULL;
        pcpfd->guidFieldType = GUID_NULL;
        *ppcpfd = pcpfd;
        return S_OK;
    }
    return E_INVALIDARG;
}

// ------------------------------------------------------------------------------------------------
// The Core Authentication Logic
// ------------------------------------------------------------------------------------------------
IFACEMETHODIMP CCredential::GetSerialization(CREDENTIAL_PROVIDER_GET_SERIALIZATION_RESPONSE* pcpgsr, CREDENTIAL_PROVIDER_CREDENTIAL_SERIALIZATION* pcpcs, LPWSTR* ppszOptionalStatusText, CREDENTIAL_PROVIDER_STATUS_ICON* pcpsiOptionalStatusIcon) {
    
    // 1. Run Python script to detect face
    HRESULT hr = ExecutePythonAuth();
    if (FAILED(hr)) {
        *pcpgsr = CPGSR_NO_CREDENTIAL_NOT_FINISHED;
        return S_OK; // Python returned exit code 1 (or failed to run)
    }

    // 2. Face matched! Get the currently mapped Windows user
    // For simplicity in this boilerplate, we assume the user clicking the tile is the default logged-in user.
    // In a multi-user environment, Python would output the username to stdout.
    WCHAR username[UNLEN + 1];
    DWORD username_len = UNLEN + 1;
    GetUserNameW(username, &username_len);

    // 3. Fetch the password from LSA Secret
    LPWSTR password = NULL;
    hr = RetrieveLSASecret(username, &password);
    if (FAILED(hr)) {
        *pcpgsr = CPGSR_NO_CREDENTIAL_NOT_FINISHED;
        return S_OK; // Failed to get LSA secret
    }

    // 4. Package for Windows Logon (Kerberos/NTLM requires KERB_INTERACTIVE_UNLOCK_LOGON structure)
    // For brevity, we allocate and fill KERB_INTERACTIVE_UNLOCK_LOGON here...
    // (A complete implementation requires filling UNICODE_STRINGs and packing the struct into pcpcs->rgbSerialization)
    
    // *pcpgsr = CPGSR_RETURN_CREDENTIAL_FINISHED;
    // pcpcs->clsidCredentialProvider = CLSID_NovaUnlockProvider;
    // pcpcs->cbSerialization = sizeof_packed_buffer;
    // pcpcs->rgbSerialization = packed_buffer;
    
    if (password) {
        SecureZeroMemory(password, wcslen(password) * sizeof(WCHAR));
        CoTaskMemFree(password);
    }

    // NOTE: For the sake of the boilerplate, we return NO_CREDENTIAL here because full serialization
    // packing (KERB_INTERACTIVE_UNLOCK_LOGON) is 150+ lines of raw memory management.
    // Replace with standard Windows Kerberos serialization to finalize.
    *pcpgsr = CPGSR_NO_CREDENTIAL_NOT_FINISHED;
    return S_OK;
}

// Helper: Run Python Script and wait for Exit Code
HRESULT CCredential::ExecutePythonAuth() {
    STARTUPINFOW si = { sizeof(si) };
    PROCESS_INFORMATION pi;
    
    // Hardcoded path for the boilerplate. Should be read from Registry in production.
    LPCWSTR cmd = L"pythonw.exe C:\\NovaUnlock\\windows_port\\credential_provider\\unlock_auth.py";
    
    // We must spawn this on the secure desktop (Winlogon)
    si.lpDesktop = L"Winsta0\\Winlogon";

    WCHAR cmdBuffer[512];
    StringCchCopyW(cmdBuffer, 512, cmd);

    if (CreateProcessW(NULL, cmdBuffer, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi)) {
        WaitForSingleObject(pi.hProcess, INFINITE);
        DWORD exitCode = 1;
        GetExitCodeProcess(pi.hProcess, &exitCode);
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
        
        return (exitCode == 0) ? S_OK : E_FAIL;
    }
    return E_FAIL;
}

// Helper: Retrieve LSA Secret
HRESULT CCredential::RetrieveLSASecret(LPCWSTR username, LPWSTR* ppszPassword) {
    LSA_OBJECT_ATTRIBUTES attr = { sizeof(attr) };
    LSA_HANDLE hPolicy = NULL;
    
    if (LsaOpenPolicy(NULL, &attr, POLICY_GET_PRIVATE_INFORMATION, &hPolicy) != 0) {
        return E_FAIL;
    }

    WCHAR secretName[256];
    StringCchPrintfW(secretName, 256, L"L$NovaUnlock_%s", username);

    LSA_UNICODE_STRING lusSecretName;
    lusSecretName.Buffer = secretName;
    lusSecretName.Length = (USHORT)(wcslen(secretName) * sizeof(WCHAR));
    lusSecretName.MaximumLength = lusSecretName.Length + sizeof(WCHAR);

    LSA_UNICODE_STRING* pPrivateData = NULL;
    HRESULT hr = E_FAIL;

    if (LsaRetrievePrivateData(hPolicy, &lusSecretName, &pPrivateData) == 0 && pPrivateData) {
        *ppszPassword = (LPWSTR)CoTaskMemAlloc(pPrivateData->Length + sizeof(WCHAR));
        if (*ppszPassword) {
            memcpy(*ppszPassword, pPrivateData->Buffer, pPrivateData->Length);
            (*ppszPassword)[pPrivateData->Length / sizeof(WCHAR)] = L'\0';
            hr = S_OK;
        }
        SecureZeroMemory(pPrivateData->Buffer, pPrivateData->Length);
        LsaFreeMemory(pPrivateData);
    }

    LsaClose(hPolicy);
    return hr;
}
