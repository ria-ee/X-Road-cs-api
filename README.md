# Central Server API

## Developing

In order to develop on your machine and test on central server you need to add your public SSH key to the server:
```bash
ssh-keygen
ssh-copy-id riajenk@xtee7.ci.kit
```

Prepare server:
```bash
sudo apt-get install python3.4-venv
```

Then create a "Run Configuration" that executes `remote_exec.sh`

