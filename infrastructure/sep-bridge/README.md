# Iran SEP Bridge

A secure, authenticated bridge for Saman Bank (SEP) payments.

## Deployment

### Dependencies
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip curl ufw
```

### Setup
1. Create user `sepbridge`:
   ```bash
   sudo useradd --system --create-home --home-dir /opt/sep-bridge --shell /usr/sbin/nologin sepbridge
   ```
2. Run `deploy.sh` (as root or with sudo):
   ```bash
   sudo chmod +x deploy.sh
   sudo ./deploy.sh
   ```
3. Edit `/opt/sep-bridge/.env` with your production credentials.
4. Generate a secure API key for authentication:
   ```bash
   openssl rand -hex 32
   ```
   Add this to `.env` as `BRIDGE_API_KEY`.
5. Restart service:
   ```bash
   sudo systemctl restart sep-bridge
   ```

### Firewall (UFW)
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
# Allow ONLY NL VPS Public IP (replace with actual IP)
sudo ufw allow from <NL_VPS_PUBLIC_IP> to any port 8443 proto tcp
sudo ufw enable
```
