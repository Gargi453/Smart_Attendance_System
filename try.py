import requests

response = requests.post("http://10.110.121.30/receive_flask_ip", json={"ip": "10.110.121.164"})
print("Status:", response.status_code)
print("Response:", response.text)
