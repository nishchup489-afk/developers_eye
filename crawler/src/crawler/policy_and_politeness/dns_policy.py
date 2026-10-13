import ipaddress 
from urllib.parse import urlsplit

"""
IP address  	Classification	            Allow?
8.8.8.8     	Public IPv4	                  Yes
1.1.1.1     	Public IPv4 	            Yes
127.0.0.1      	Loopback	                 No
192.168.1.1 	Private network	            No
10.0.0.5    	Private network	            No
169.254.169.254	Link-local	                No
100.64.0.1	    Shared address space	    No
224.0.0.1	    Multicast	                 No
::1	            IPv6 loopback	             No
2606:4700:4700::1111	Public IPv6	Yes
"""


def is_public_ip(address : str) -> bool:
    if not isinstance(address , str) or not address:
        return False 

    if "%" in address:
        return False 

    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False 


    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped 

        elif ip.sixtofour is not None or ip.teredo is not None:
            return False 


    return (
        ip.is_global
        and not ip.is_multicast 
        and not ip.is_reserved
    )



async def resolve_hostname(url : str ) -> list[ip]:
    domain_name = urlsplit(url).netloc
    