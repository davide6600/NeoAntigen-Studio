#!/bin/bash
# NeoAntigen-Studio — NetMHCpan 4.1 Installation Guide
# PREREQUISITI:
# 1. Registrati su: https://services.healthtech.dtu.dk/services/NetMHCpan-4.1/
# 2. Scarica netMHCpan-4.1b.Linux.tar.gz nella directory corrente
# 3. Esegui questo script: bash scripts/install_netmhcpan.sh
#
set -e

INSTALL_DIR="${NETMHCPAN_INSTALL_DIR:-/opt/netMHCpan}"
ARCHIVE="netMHCpan-4.1b.Linux.tar.gz"

if [ ! -f "$ARCHIVE" ]; then
    echo "ERROR: $ARCHIVE not found."
    echo "Download from: https://services.healthtech.dtu.dk/services/NetMHCpan-4.1/"
    exit 1
fi

echo "Installing NetMHCpan 4.1 to $INSTALL_DIR..."
sudo mkdir -p "$INSTALL_DIR"
sudo tar -xzf "$ARCHIVE" -C "$INSTALL_DIR" --strip-components=1

# Configura TMPDIR nel script NetMHCpan
sudo sed -i "s|setenv  TMPDIR.*|setenv  TMPDIR /tmp|" "$INSTALL_DIR/netMHCpan"
sudo sed -i "s|set NMHOME.*|set NMHOME $INSTALL_DIR|" "$INSTALL_DIR/netMHCpan"

# Symlink in PATH
sudo ln -sf "$INSTALL_DIR/netMHCpan" /usr/local/bin/netMHCpan

# Verifica
echo "Testing NetMHCpan installation..."
echo "SIINFEKL" > /tmp/test_peptide.txt
netMHCpan -a HLA-A02:01 -f /tmp/test_peptide.txt -p && \
    echo "✅ NetMHCpan installed and working!" || \
    echo "❌ Installation may have issues — check manually"

echo ""
echo "Add to .env:"
echo "NETMHCPAN_PATH=/usr/local/bin/netMHCpan"
