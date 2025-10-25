#!/bin/bash

echo "=================================================="
echo "Hephaestus Multicast Discovery Fix Script"
echo "=================================================="
echo ""

# Detect Python path
PYTHON_PATH=$(which python3)
PYTHON_REAL_PATH=$(readlink -f "$PYTHON_PATH" 2>/dev/null || realpath "$PYTHON_PATH" 2>/dev/null || echo "$PYTHON_PATH")

echo "Detected Python path: $PYTHON_REAL_PATH"
echo ""

# Check if firewall is enabled
FIREWALL_STATE=$(/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate | grep -o "State = [0-9]" | cut -d' ' -f3)

if [ "$FIREWALL_STATE" = "1" ]; then
    echo "✓ Firewall is enabled"
    echo ""
    echo "Adding Python to firewall allowed apps..."
    echo ""

    # Add Python to firewall
    sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add "$PYTHON_REAL_PATH" 2>&1
    sudo /usr/libexec/ApplicationFirewall/socketfilterfw --unblockapp "$PYTHON_REAL_PATH" 2>&1

    echo ""
    echo "✓ Python added to firewall exceptions"
else
    echo "✗ Firewall is disabled, no action needed"
fi

echo ""
echo "=================================================="
echo "Checking network configuration..."
echo "=================================================="
echo ""

# Get local IP
LOCAL_IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | grep -v "inet 100\." | head -1 | awk '{print $2}')

if [ -z "$LOCAL_IP" ]; then
    echo "✗ Could not detect local IP address"
    echo "  Please set PUBLIC_IP manually in .env file"
else
    echo "✓ Detected local IP: $LOCAL_IP"

    # Check if .env exists
    if [ -f ".env" ]; then
        # Check if PUBLIC_IP is set
        CURRENT_IP=$(grep "^PUBLIC_IP=" .env | cut -d'=' -f2)

        if [ "$CURRENT_IP" = "$LOCAL_IP" ]; then
            echo "✓ PUBLIC_IP already set correctly in .env: $LOCAL_IP"
        else
            echo ""
            echo "Current PUBLIC_IP in .env: $CURRENT_IP"
            read -p "Update PUBLIC_IP to $LOCAL_IP? (y/n) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                # Update PUBLIC_IP in .env
                if grep -q "^PUBLIC_IP=" .env; then
                    sed -i.bak "s/^PUBLIC_IP=.*/PUBLIC_IP=$LOCAL_IP/" .env
                else
                    echo "PUBLIC_IP=$LOCAL_IP" >> .env
                fi
                echo "✓ Updated PUBLIC_IP in .env to $LOCAL_IP"
            fi
        fi
    else
        echo "✗ .env file not found"
        echo "  Please create .env from .env.hotspot template"
    fi
fi

echo ""
echo "=================================================="
echo "Multicast route check..."
echo "=================================================="
echo ""

# Check multicast route
MCAST_ROUTE=$(netstat -rn | grep "224.0.0/4" | grep -v "utun")

if [ -z "$MCAST_ROUTE" ]; then
    echo "✗ No multicast route found"
else
    echo "✓ Multicast routes:"
    echo "$MCAST_ROUTE"
fi

echo ""
echo "=================================================="
echo "Setup complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "1. Restart the Hephaestus app: python -m backend.app"
echo "2. Run this script on ALL nodes in your mesh network"
echo "3. Check logs for: 'Joined multicast group 224.0.0.251 on interface <YOUR_IP>'"
echo ""
