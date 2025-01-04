import re
import requests
from bs4 import BeautifulSoup
from colorama import Fore

website = "https://miportal.entel.pe/personas/catalogo/postpago/renovacion"
result = requests.get(website)
content = result.text
print(content)