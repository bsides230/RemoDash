# RemoDash systemd service installer

This script installs RemoDash as a persistent `systemd` service so it:

- starts automatically on boot
- keeps running after SSH is closed
- restarts automatically if it crashes

## Files

- `install_remodash_service.py`

## Usage

Make sure RemoDash is already installed and working:

```bash
git clone https://github.com/bsides230/RemoDash.git
cd RemoDash
pip3 install --break-system-packages -r requirements.txt
python3 server.py
```

If that works, stop it and run:

```bash
python3 install_remodash_service.py
```

## Options

```bash
--service-name remodash
--app-dir /home/user/RemoDash
--user username
--entry-file server.py
```

## Useful commands

Check status:

```bash
sudo systemctl status remodash
```

Logs:

```bash
journalctl -u remodash -f
```

Restart:

```bash
sudo systemctl restart remodash
```

Stop:

```bash
sudo systemctl stop remodash
```
