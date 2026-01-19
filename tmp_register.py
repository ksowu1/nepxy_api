import requests
accounts=[
  { email:ksowu190@gmail.com,phone_e164:+15550000000,country:TG,password:redmoon1},
  {email:admin@nexapay.io,phone_e164:+15550000001,country:TG,password:redmoon1A!}
]
for payload in accounts:
  resp = requests.post('http://127.0.0.1:8001/v1/auth/register', json=payload)
  print(payload['email'], resp.status_code, resp.text)
