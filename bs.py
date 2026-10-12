from urllib.parse import urlsplit 

url = "HTTPS://EXAMPLE.COM:443/docs?lang=en#intro"

print(urlsplit(url))