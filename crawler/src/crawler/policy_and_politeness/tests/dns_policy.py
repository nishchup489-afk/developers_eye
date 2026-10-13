from crawler.policy_and_politeness.dns_policy import is_public_ip
from colorama import init , Fore 

init(autoreset=True)


tests = {
    "8.8.8.8": True,
    "1.1.1.1": True,
    "127.0.0.1": False,
    "192.168.1.1": False,
    "10.0.0.5": False,
    "169.254.169.254": False,
    "100.64.0.1": False,
    "224.0.0.1": False,
    "::1": False,
    "fe80::1": False,
    "2606:4700:4700::1111": True,
    "::ffff:127.0.0.1": False,
    "invalid-ip": False,
}

for address, expected in tests.items():
    result = is_public_ip(address)
    assert result == expected, address

print(Fore.GREEN + "All IP validation tests passed.")