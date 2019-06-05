# Central Server API

## API description

API is described using OpenAPI specification: [openapi-definition.yaml](openapi-definition.yaml)

## Systemd configuration

Add service description `systemd/csapi.service` to `/lib/systemd/system/csapi.service`. Then start and enable automatic startup:
```bash
sudo systemctl daemon-reload
sudo systemctl start csapi
sudo systemctl enable csapi
```

## Nginx configuration

Create a certificate for nginx:
```bash
mkdir -p /etc/nginx/csapi
cd /etc/nginx/csapi
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout csapi.key -out csapi.crt
```

Cert info (NB! CN should be the domain name of your central server):
```
Country Name (2 letter code) [AU]:EE
State or Province Name (full name) [Some-State]:Harjumaa
Locality Name (eg, city) []:Tallinn
Organization Name (eg, company) [Internet Widgits Pty Ltd]:RIA
Organizational Unit Name (eg, section) []:CSAPI
Common Name (e.g. server FQDN or YOUR name) []:central-server.ci.kit
Email Address []:
```

Make sure key is accessible to nginx:
```bash
sudo chgrp www-data /etc/nginx/csapi/csapi.key
sudo chmod g+r /etc/nginx/csapi/csapi.key
```

On client side (XTSS app):
```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout client.key -out client.crt 
```

Cert info:
```
Country Name (2 letter code) [AU]:EE
State or Province Name (full name) [Some-State]:Harjumaa
Locality Name (eg, city) []:Tallinn
Organization Name (eg, company) [Internet Widgits Pty Ltd]:RIA
Organizational Unit Name (eg, section) []:xtss
Common Name (e.g. server FQDN or YOUR name) []:
Email Address []:
```

Copy client.crt to nginx machine: `/etc/nginx/csapi/client.crt`

For testing copy nginx `csapi.crt` to client and issue curl command:
```bash
curl --cert client.crt --key client.key --cacert csapi.crt -i -d '{"member_code": "XX000003", "member_name": "XX Test 3", "member_class": "GOVXXX"}' -X POST https://jan-center2.ci.kit:5443/member
```

Add nginx configuration from this repository: `nginx/csapi` to nginx server: `/etc/nginx/sites-enabled/csapi`

## Testing
Note that `server.py` is a configuration file for logging and flask and therefore not covered by tests.

Running the tests:
```bash
cd <project_directory>
python -m unittest
```

Or alternatively run the test file directly:
```bash
python test_member.py
```

In order to measure code coverage install `coverage` module:
```bash
pip install coverage
```

Then coverage analyse:
```bash
coverage run test_member.py
coverage report member.py
```

Alternatively you can generate html report with:
```bash
coverage html member.py
```

In order to lint the code install `pylint` module:
```bash
pip install pylint
```

Then run the analyse:
```bash
pylint member.py
```
