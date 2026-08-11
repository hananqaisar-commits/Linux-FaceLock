import ctypes
from ctypes import wintypes
import getpass
import os

# Define required structures and constants for LSA API
advapi32 = ctypes.WinDLL('advapi32')

class LSA_UNICODE_STRING(ctypes.Structure):
    _fields_ = [
        ('Length', wintypes.USHORT),
        ('MaximumLength', wintypes.USHORT),
        ('Buffer', ctypes.c_wchar_p),
    ]

class LSA_OBJECT_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ('Length', wintypes.ULONG),
        ('RootDirectory', wintypes.HANDLE),
        ('ObjectName', ctypes.POINTER(LSA_UNICODE_STRING)),
        ('Attributes', wintypes.ULONG),
        ('SecurityDescriptor', wintypes.LPVOID),
        ('SecurityQualityOfService', wintypes.LPVOID),
    ]

POLICY_CREATE_SECRET = 0x0020

def InitLsaString(lsa_string, string):
    if string is None:
        lsa_string.Buffer = None
        lsa_string.Length = 0
        lsa_string.MaximumLength = 0
        return
    lsa_string.Buffer = string
    lsa_string.Length = len(string) * ctypes.sizeof(ctypes.c_wchar)
    lsa_string.MaximumLength = lsa_string.Length + ctypes.sizeof(ctypes.c_wchar)

def store_lsa_secret(secret_name, secret_value):
    lsa_name = LSA_UNICODE_STRING()
    InitLsaString(lsa_name, secret_name)

    lsa_data = LSA_UNICODE_STRING()
    InitLsaString(lsa_data, secret_value)

    obj_attr = LSA_OBJECT_ATTRIBUTES()
    obj_attr.Length = ctypes.sizeof(LSA_OBJECT_ATTRIBUTES)
    obj_attr.RootDirectory = None
    obj_attr.ObjectName = None
    obj_attr.Attributes = 0
    obj_attr.SecurityDescriptor = None
    obj_attr.SecurityQualityOfService = None

    policy_handle = wintypes.HANDLE()

    # Open the local LSA Policy
    status = advapi32.LsaOpenPolicy(
        None,
        ctypes.byref(obj_attr),
        POLICY_CREATE_SECRET,
        ctypes.byref(policy_handle)
    )

    if status != 0:
        print(f"[-] Failed to open LSA Policy. Error: {advapi32.LsaNtStatusToWinError(status)}")
        print("    Make sure you run this script as Administrator!")
        return False

    # Store the private data (LSA Secret)
    status = advapi32.LsaStorePrivateData(
        policy_handle,
        ctypes.byref(lsa_name),
        ctypes.byref(lsa_data)
    )

    advapi32.LsaClose(policy_handle)

    if status != 0:
        print(f"[-] Failed to store LSA Secret. Error: {advapi32.LsaNtStatusToWinError(status)}")
        return False

    return True

if __name__ == "__main__":
    import platform
    if platform.system() != "Windows":
        print("This tool is for Windows only.")
        exit(1)

    # Check for Admin privileges
    if not ctypes.windll.shell32.IsUserAnAdmin():
        print("[-] This script requires Administrator privileges to write LSA Secrets.")
        print("    Please run terminal as Administrator and try again.")
        exit(1)

    print("=============================================")
    print(" NovaUnlock - Windows Password Enrollment")
    print("=============================================")
    print("Your password is required to unlock Windows natively.")
    print("It will be encrypted and stored in the Local Security Authority (LSA).")
    print("It is never saved to a plaintext file.")
    print("---------------------------------------------")

    user = os.environ.get("USERNAME", "user")
    
    pwd1 = getpass.getpass(f"Enter Windows Password for {user}: ")
    pwd2 = getpass.getpass("Confirm Password: ")

    if pwd1 != pwd2:
        print("[-] Passwords do not match. Aborting.")
        exit(1)

    # The prefix L$ ensures only SYSTEM can read it
    secret_key = f"L$NovaUnlock_{user}"
    
    if store_lsa_secret(secret_key, pwd1):
        print("[+] SUCCESS! Password securely stored in LSA Secret.")
        print(f"    Secret Key: {secret_key}")
    else:
        print("[-] Failed to enroll password.")
