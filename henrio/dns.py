"""
https://github.com/eklitzke/gaia/blob/master/gaia.py
Python ctypes implementation of getaddrinfo_a.
This wraps the GNU libc implementation of getaddrinfo_a, with a simple
interface. The module exports a single function, get_records, which looks up
multiple DNS names in parallel.
Again, this will only work on systems whose libc implementation is glibc, and
it will probably only work on Linux systems (since the sonames are hardcoded).
This code is based on the example code in the getaddrinfo_a man page, and is
released to the public domain.
"""

import ctypes
from types import coroutine

from .yields import get_loop

try:
    libc = ctypes.cdll.LoadLibrary('libc.so.6')
    libanl = ctypes.cdll.LoadLibrary('libanl.so.1')
    winsock = None
except OSError:
    pass
    libc = None
    libanl = None
    winsock = None
    _overlapped = None
    '''
    try:
        winsock = ctypes.windll.LoadLibrary("Ws2_32.dll")
        import ctypes.wintypes as wintypes
        import _overlapped
    except ImportError:
        winsock = None
        _overlapped = None
    '''

if libc:
    # these constants cribbed from libanl
    GAI_WAIT = 0
    GAI_NOWAIT = 1
    NI_MAXHOST = 1025
    NI_NUMERICHOST = 1


    class addrinfo(ctypes.Structure):
        _fields_ = [
            ('ai_flags', ctypes.c_int),
            ('ai_family', ctypes.c_int),
            ('ai_socktype', ctypes.c_int),
            ('ai_protocol', ctypes.c_int),
            ('ai_addrlen', ctypes.c_size_t),
            ('ai_addr', ctypes.c_void_p),
            ('ai_canonname', ctypes.c_char_p),
            ('ai_next', ctypes.c_void_p)
        ]


    c_addrinfo_p = ctypes.POINTER(addrinfo)


    class gaicb(ctypes.Structure):
        _fields_ = [
            ('ar_name', ctypes.c_char_p),
            ('ar_service', ctypes.c_char_p),
            ('ar_request', c_addrinfo_p),
            ('ar_result', c_addrinfo_p)
        ]


    c_gaicb_p = ctypes.POINTER(gaicb)

    getaddrinfo_a = libanl.getaddrinfo_a
    getaddrinfo_a.argtypes = [ctypes.c_int,  # mode
                              ctypes.POINTER(c_gaicb_p),  # list
                              ctypes.c_int,  # nitems
                              ctypes.c_void_p  # sevp
                              ]
    getaddrinfo_a.restype = ctypes.c_int

    getnameinfo = libc.getnameinfo
    getnameinfo.argtypes = [ctypes.c_void_p,  # sa
                            ctypes.c_size_t,  # salen
                            ctypes.c_char_p,  # host
                            ctypes.c_size_t,  # hostlen
                            ctypes.c_char_p,  # serv
                            ctypes.c_size_t,  # servlen
                            ctypes.c_int  # flags
                            ]
    getnameinfo.restype = ctypes.c_int

    # statically allocate the host array
    host = ctypes.cast((ctypes.c_char * NI_MAXHOST)(), ctypes.c_char_p)

    gai_cancel = libanl.gai_cancel
    gai_cancel.argtypes = [gaicb]



    @coroutine
    def getaddrinfo_a(hostname, timeout=-1):
        """A getaddrinfo for systems supporting `getaddrinfo_a`. """
        loop = yield from get_loop()
        etime = loop.time() + timeout
        names = [hostname]
        reqs = (c_gaicb_p * 1)()
        for i, name in enumerate(names):
            g = gaicb()
            ctypes.memset(ctypes.byref(g), 0, ctypes.sizeof(gaicb))
            g.ar_name = hostname.encode()
            reqs[i] = ctypes.pointer(g)

        # get the records; this does i/o and does not block
        ret = getaddrinfo_a(GAI_NOWAIT, reqs, 1, None)
        assert ret == 0

        # parse the records out of all the structs
        while timeout == -1 or etime > loop.time():
            try:
                for req in reqs:
                    res = req.contents.ar_result.contents
                    ret = getnameinfo(res.ai_addr, res.ai_addrlen,
                                      host, NI_MAXHOST, None, 0, NI_NUMERICHOST)
                    assert ret == 0
                    return host.value
            except ValueError:
                yield
        else:
            try:
                gai_cancel(reqs)
            except Exception as e:
                print(e)
            raise TimeoutError

if False:  # winsock:
    class GUID(ctypes.Structure):
        _fields_ = [
            ('Data1', ctypes.c_ulong),
            ('Data2', ctypes.c_ushort),
            ('Data3', ctypes.c_ushort),
            ('Data4[8]', ctypes.c_byte),
        ]


    class addrinfoEx(ctypes.Structure):
        _fields_ = [
            ('ai_flags', ctypes.c_int),
            ('ai_family', ctypes.c_int),
            ('ai_socktype', ctypes.c_int),
            ('ai_protocol', ctypes.c_int),
            ('ai_addrlen', ctypes.c_size_t),
            ('ai_canonname', ctypes.c_char_p),
            ('ai_addr', ctypes.c_void_p),
            ('ai_blob', ctypes.c_void_p),
            ('ai_bloblen', ctypes.c_size_t),
            ('ai_provider', GUID),
            ('ai_next', ctypes.c_void_p)
        ]


    c_addrinfoEx_p = ctypes.POINTER(addrinfoEx)

    getaddrinfoex = winsock.GetAddrInfoExW
    getaddrinfoex.argtypes = [
        ctypes.c_char_p,  # pName
        ctypes.c_char_p,  # pServiceName
        wintypes.DWORD,  # dwNamespace
        ctypes.c_void_p,  # GUID,  # lpNspId
        ctypes.POINTER(c_addrinfoEx_p),  # addrinfoEx,  # pHints,
        ctypes.c_void_p,  # ppResult
        ctypes.c_void_p,  # timeout
        ctypes.c_void_p,  # lpOverlapped
        ctypes.c_void_p,  # lpCompletionRoutine
        wintypes.LPHANDLE,  # lpHandle
    ]

    winsock.WSAEnumProtocolsW

