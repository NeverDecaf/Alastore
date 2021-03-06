#http://stackoverflow.com/questions/4662759/how-to-change-folder-icons-with-python-on-windows
import os
import ctypes
from ctypes import POINTER, Structure, c_wchar, c_int, sizeof, byref
from ctypes.wintypes import BYTE, WORD, DWORD, LPWSTR, LPSTR
##import win32api    

# in case it wasnt apparent, this will only work on windows.

HICON = c_int
LPTSTR = LPWSTR
TCHAR = c_wchar
MAX_PATH = 260
FCSM_ICONFILE = 0x00000010
FCS_FORCEWRITE = 0x00000002
SHGFI_ICONLOCATION = 0x000001000    

class GUID(Structure):
    _fields_ = [
        ('Data1', DWORD),
        ('Data2', WORD),
        ('Data3', WORD),
        ('Data4', BYTE * 8)]

class SHFOLDERCUSTOMSETTINGS(Structure):
    _fields_ = [
        ('dwSize', DWORD),
        ('dwMask', DWORD),
        ('pvid', POINTER(GUID)),
        ('pszWebViewTemplate', LPTSTR),
        ('cchWebViewTemplate', DWORD),
        ('pszWebViewTemplateVersion', LPTSTR),
        ('pszInfoTip', LPTSTR),
        ('cchInfoTip', DWORD),
        ('pclsid', POINTER(GUID)),
        ('dwFlags', DWORD),
        ('pszIconFile', LPTSTR),
        ('cchIconFile', DWORD),
        ('iIconIndex', c_int),
        ('pszLogo', LPTSTR),
        ('cchLogo', DWORD)]

class SHFILEINFO(Structure):
    _fields_ = [
        ('hIcon', HICON),
        ('iIcon', c_int),
        ('dwAttributes', DWORD),
        ('szDisplayName', TCHAR * MAX_PATH),
        ('szTypeName', TCHAR * 80)]    

def seticon(folderpath, iconpath, iconindex, relative=1):
    """Set folder icon.

    >>> seticon(".", "C:\\Windows\\system32\\SHELL32.dll", 10)

    """
    shell32 = ctypes.windll.shell32

    folderpath = str(os.path.abspath(folderpath), 'mbcs')
    if relative:
        iconpath = str(os.path.join('.',os.path.basename(iconpath)), 'mbcs')
    else:
        iconpath = str(os.path.abspath(iconpath), 'mbcs')
    
    fcs = SHFOLDERCUSTOMSETTINGS()
    fcs.dwSize = sizeof(fcs)
    fcs.dwMask = FCSM_ICONFILE
    fcs.pszIconFile = iconpath
    fcs.cchIconFile = 0
    fcs.iIconIndex = iconindex

    hr = shell32.SHGetSetFolderCustomSettings(byref(fcs), folderpath,
                                              FCS_FORCEWRITE)
    if hr:
        raise WindowsError()#win32api.FormatMessage(hr))

    sfi = SHFILEINFO()
    hr = shell32.SHGetFileInfoW(folderpath, 0, byref(sfi), sizeof(sfi),
                                SHGFI_ICONLOCATION)
    if hr == 0:
        raise WindowsError()#win32api.FormatMessage(hr))

    index = shell32.Shell_GetCachedImageIndexW(sfi.szDisplayName, sfi.iIcon, 0)
    if index == -1:
        raise WindowsError()

    shell32.SHUpdateImageW(sfi.szDisplayName, sfi.iIcon, 0, index)

def seticon_unicode(folderpath, iconpath, iconindex, relative=1):
    # tried to hack together a version that assumes strings are already unicode, will probably not work.
    # it works.
    """Set folder icon.

    >>> seticon(".", "C:\\Windows\\system32\\SHELL32.dll", 10)

    """
    shell32 = ctypes.windll.shell32

    folderpath = os.path.abspath(folderpath)
    if relative:
        iconpath = os.path.join('.',os.path.basename(iconpath))
    else:
        iconpath = os.path.abspath(iconpath)
    
    fcs = SHFOLDERCUSTOMSETTINGS()
    fcs.dwSize = sizeof(fcs)
    fcs.dwMask = FCSM_ICONFILE
    fcs.pszIconFile = iconpath
    fcs.cchIconFile = 0
    fcs.iIconIndex = iconindex

    hr = shell32.SHGetSetFolderCustomSettings(byref(fcs), folderpath,
                                              FCS_FORCEWRITE)
    if hr:
        raise WindowsError()#win32api.FormatMessage(hr))

    sfi = SHFILEINFO()
    hr = shell32.SHGetFileInfoW(folderpath, 0, byref(sfi), sizeof(sfi),
                                SHGFI_ICONLOCATION)
    if hr == 0:
        raise WindowsError()#win32api.FormatMessage(hr))

    shell32.SHUpdateImageA(sfi.szDisplayName, 0, 0, 0)
    

##    index = shell32.Shell_GetCachedImageIndexW(sfi.szDisplayName, sfi.iIcon, 0)
##    if index == -1:
##        raise WindowsError()
##
##    shell32.SHUpdateImageW(sfi.szDisplayName, sfi.iIcon, 0, index)
    
if __name__=='__main__':
    import sys
    if len(sys.argv)==3:
        seticon_unicode(sys.argv[1],sys.argv[2],0)
        'path,icon_path'
