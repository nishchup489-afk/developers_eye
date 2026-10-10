from urllib.parse import urldefrag 

url = "HTTPS://EXAMPLE.COM:443/docs?lang=en#intro"

print(urldefrag(url))