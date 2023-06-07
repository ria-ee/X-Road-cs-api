# Central Server API

This API can be used to add new X-Road members and subsystems directly to X-Road Central Server without web admin interface. API is compatible with X-Road versions 7.3+ and is using an official management API for Central Server to save data.

The advantage of using this API in favor of official API is compatibility with previous versions of CS API, possibility to use TLS certificates for authentication and limiting access to Central Server API to only required functionality. For example when using official management API client application would be able not only to add new members and clients but additionally to delete them and perform various other actions in Central Server.

For Central Server versions prior to 7.3 use older version of CS API.

**NB! Make sure your API is not accessible from public internet, and is properly secured in your internal network!**

## API description

API is described using OpenAPI specification: [openapi-definition.yaml](openapi-definition.yaml)

## Installation

Installation was tested with Ubuntu 20.04 and Python 3.8.

### Program

Provided systemd and nginx configurations assume than program files are installed under `/opt/csapi`. Program is running under `xroad` user to be able to access X-Road configuration files and database without any additional configurations.

Create `/opt/csapi` and `/opt/csapi/socket` directories:
```bash
sudo mkdir -p /opt/csapi
sudo mkdir -p /opt/csapi/socket
sudo chown xroad /opt/csapi/socket/
```

And copy files `csapi.py` and `requirements.txt` into `/opt/csapi` directory.

You will need to install support for python venv:
```bash
sudo apt-get install python3-venv
```

Then install required python modules into venv:
```bash
cd /opt/csapi
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create configuration file `/opt/csapi/config.yaml` based on example configuration `example-config.yaml`. You need to either set parameter "allow_all" to "true" to disable client certificate check or specify list of trusted Client DN's. Disabled check means that all certificates trusted by Nginx would be allowed.

### Systemd configuration

Add service description `systemd/csapi.service` to `/lib/systemd/system/csapi.service`. Then start and enable automatic startup:
```bash
sudo systemctl daemon-reload
sudo systemctl start csapi
sudo systemctl enable csapi
```

### Nginx configuration

Add nginx configuration from this repository: `nginx/csapi.conf` to nginx server: `/etc/nginx/sites-enabled/csapi.conf`

Create a certificate for nginx (installed by default in X-Road Central Server):
```bash
sudo mkdir -p /etc/nginx/csapi
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
Common Name (e.g. server FQDN or YOUR name) []:central-server.domain.local
Email Address []:
```

Make sure key is accessible to nginx:
```bash
sudo chmod 640 /etc/nginx/csapi/csapi.key
sudo chgrp www-data /etc/nginx/csapi/csapi.key
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
Organizational Unit Name (eg, section) []:APIClient
Common Name (e.g. server FQDN or YOUR name) []:
Email Address []:
```

Copy client.crt to Central Server machine: `/etc/nginx/csapi/client.crt`

For testing copy nginx `csapi.crt` to client and issue curl commands:
```bash
curl --cert client.crt --key client.key --cacert csapi.crt -i -d '{"member_class": "GOVXXX", "member_code": "XX000003", "member_name": "XX Test 3"}' -X POST https://central-server.domain.local:5443/member
curl --cert client.crt --key client.key --cacert csapi.crt -i -d '{"member_class": "GOVXXX", "member_code": "XX000003", "subsystem_code": "SystemXX"}' -X POST https://central-server.domain.local:5443/subsystem
```

Note that you can allow multiple clients (or nodes) by creating certificate bundle. That can be done by concatenating multiple client certificates into single `client.crt` file.

### API Status
API Status is available on `/status` endpoint. You can test that with curl:
```bash
curl -k https://central-server.domain.local:5443/status
```

## Testing

Install required python modules and dev tools into venv:
```bash
cd <project_directory>
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements_dev_tools.txt
```

Running the tests:
```bash
cd <project_directory>
python -m unittest
```

Or alternatively run the test file directly:
```bash
python test_csapi.py
```

In order to measure code coverage run:
```bash
coverage run test_csapi.py
coverage report csapi.py
```

Alternatively you can generate html report with:
```bash
coverage run test_csapi.py
coverage html csapi.py
```

In order to lint the code run:
```bash
pylint csapi.py
```

# Freezing requirements

In order to freeze python requirements so that production would have only module versions tested in dev/test environments you can create new venv and run pip freeze:
```bash
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip freeze -r requirements.txt -l > requirements_freeze.txt
```

Then you can install python requirements using `requirements_freeze.txt` file instead of `requirements.txt`
