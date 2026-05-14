import urllib.request
r = urllib.request.urlopen('https://api.telegram.org/bot8691159247:AAEfGEBQgXBqXvA9RCO67cFCwwtDaFrNRH4/getMe', timeout=10)
print(r.read().decode())
