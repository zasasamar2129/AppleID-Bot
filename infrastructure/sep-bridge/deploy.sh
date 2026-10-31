#!/usr/bin/env bash
set -e

echo "=== Deploying Iran SEP Bridge ==="

INSTALL_DIR="/opt/sep-bridge"

if [ ! -d "$INSTALL_DIR" ]; then
    echo "Creating deployment directory..."
    sudo mkdir -p $INSTALL_DIR
fi

echo "Copying application files..."
sudo cp -r bridge_app $INSTALL_DIR/
sudo cp requirements.txt $INSTALL_DIR/
sudo cp sep-bridge.service /etc/systemd/system/

if [ ! -f "$INSTALL_DIR/.env" ]; then
    echo "Creating initial .env file..."
    sudo cp .env.example $INSTALL_DIR/.env
    echo "IMPORTANT: Please edit $INSTALL_DIR/.env with your production secrets!"
fi

echo "Setting up virtual environment..."
if [ ! -d "$INSTALL_DIR/venv" ]; then
    sudo python3 -m venv $INSTALL_DIR/venv
fi

sudo $INSTALL_DIR/venv/bin/pip install --upgrade pip
sudo $INSTALL_DIR/venv/bin/pip install -r $INSTALL_DIR/requirements.txt

echo "Setting permissions..."
sudo chown -R sepbridge:sepbridge $INSTALL_DIR

echo "Reloading and restarting systemd service..."
sudo systemctl daemon-reload
sudo systemctl enable sep-bridge
sudo systemctl restart sep-bridge

echo "=== Deployment Complete ==="
echo "Check status with: sudo systemctl status sep-bridge"
