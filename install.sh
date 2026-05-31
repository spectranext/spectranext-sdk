#!/bin/bash
set -e

# z88dk nightly build to install.
# Keep this aligned with the Homebrew tap resource.
Z88DK_NIGHTLY_DATE="20260530"
Z88DK_NIGHTLY_COMMIT="a996c99f3d"
Z88DK_NIGHTLY_REVISION="24825"
Z88DK_NIGHTLY_ID="${Z88DK_NIGHTLY_DATE}-${Z88DK_NIGHTLY_COMMIT}-${Z88DK_NIGHTLY_REVISION}"
Z88DK_BASE_URL="http://nightly.z88dk.org"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
elif [[ "$OSTYPE" == "linux"* ]]; then
    if [ -r /etc/os-release ]; then
        . /etc/os-release
        case "${ID:-}" in
            ubuntu)
                OS="ubuntu"
                ;;
            alpine)
                OS="alpine"
                ;;
            *)
                case " ${ID_LIKE:-} " in
                    *" ubuntu "*|*" debian "*)
                        OS="ubuntu"
                        ;;
                    *)
                        echo "Error: Unsupported Linux distribution: ${ID:-unknown}"
                        exit 1
                        ;;
                esac
                ;;
        esac
    else
        echo "Error: Cannot detect Linux distribution. /etc/os-release is missing."
        exit 1
    fi
else
    echo "Error: Unsupported OS. This script supports macOS and Linux only."
    exit 1
fi

echo "Detected OS: $OS"

# Check if z88dk already exists (idempotent)
if [ -d "z88dk" ] && [ -f "z88dk/bin/zcc" ]; then
    echo "z88dk already installed, skipping..."
else
    if [ "$OS" == "macos" ]; then
        echo "Installing z88dk for macOS..."
        
        # Download pinned z88dk nightly binary release
        Z88DK_URL="${Z88DK_BASE_URL}/z88dk-osx-${Z88DK_NIGHTLY_ID}.zip"
        Z88DK_ZIP="z88dk-osx-${Z88DK_NIGHTLY_ID}.zip"
        
        if [ ! -f "$Z88DK_ZIP" ]; then
            echo "Downloading z88dk..."
            curl -L -o "$Z88DK_ZIP" "$Z88DK_URL"
        fi
        
        # Extract to z88dk folder
        echo "Extracting z88dk..."
        unzip -q -o "$Z88DK_ZIP" -d .
        # The zip might extract to a subdirectory, move contents if needed
        if [ -d "z88dk-osx-${Z88DK_NIGHTLY_ID}" ]; then
            mv "z88dk-osx-${Z88DK_NIGHTLY_ID}" z88dk
        fi
        
        # Clean up zip file
        rm -f "$Z88DK_ZIP"
        
    elif [ "$OS" == "ubuntu" ]; then
        echo "Installing z88dk for Ubuntu..."
        
        # Install build dependencies
        echo "Installing build dependencies..."
        sudo apt-get update
        sudo apt-get install -y \
            cmake git build-essential python3 python3-pip python3-venv \
            perl pkg-config libxml2-dev m4 bison flex ragel dos2unix re2c \
            libjpeg-dev zlib1g-dev libgmp-dev \
            cpanminus
        
        # Install Perl modules
        echo "Installing Perl modules..."
        sudo cpanm -n Modern::Perl YAML::Tiny CPU::Z80::Assembler || {
            echo "Warning: Some Perl modules may have failed to install, continuing..."
        }
        
        # Download pinned z88dk nightly source release
        Z88DK_URL="${Z88DK_BASE_URL}/z88dk-${Z88DK_NIGHTLY_ID}.tgz"
        Z88DK_TGZ="z88dk-${Z88DK_NIGHTLY_ID}.tgz"
        
        if [ ! -f "$Z88DK_TGZ" ]; then
            echo "Downloading z88dk source..."
            curl -L -o "$Z88DK_TGZ" "$Z88DK_URL"
        fi
        
        # Extract to z88dk-src folder
        echo "Extracting z88dk source..."
        tar -xzf "$Z88DK_TGZ"
        # The tarball might extract to a subdirectory, move contents if needed
        if [ -d "z88dk-${Z88DK_NIGHTLY_ID}" ]; then
            mv "z88dk-${Z88DK_NIGHTLY_ID}" z88dk-src
        elif [ ! -d "z88dk-src" ]; then
            # If it extracted to current directory, rename it
            if [ -d "z88dk" ] && [ ! -d "z88dk-src" ]; then
                mv z88dk z88dk-src
            fi
        fi
        
        # Build host tools only. Nightly source archives already include target libraries.
        echo "Building z88dk host tools..."
        cd z88dk-src
        chmod +x build.sh
        ./build.sh -l
        
        # Install to z88dk folder
        echo "Installing z88dk..."
        mkdir -p ../z88dk
        make PREFIX="$(cd .. && pwd)/z88dk" install
        cp -R lib ../z88dk
        cp -R include ../z88dk
        cp -R support ../z88dk

        cd ..
        
        # Clean up source and tarball
        rm -rf z88dk-src
        rm -f "$Z88DK_TGZ"
    elif [ "$OS" == "alpine" ]; then
        echo "Installing z88dk for Alpine Linux..."

        echo "Installing build dependencies..."
        apk add --no-cache \
            bash cmake git build-base python3 py3-pip py3-setuptools gmp-dev \
            libxml2 libxml2-dev m4 perl bison flex ragel perl-utils perl-dev dos2unix re2c \
            jpeg-dev zlib-dev curl

        # Download pinned z88dk nightly source release
        Z88DK_URL="${Z88DK_BASE_URL}/z88dk-${Z88DK_NIGHTLY_ID}.tgz"
        Z88DK_TGZ="z88dk-${Z88DK_NIGHTLY_ID}.tgz"

        if [ ! -f "$Z88DK_TGZ" ]; then
            echo "Downloading z88dk source..."
            curl -L -o "$Z88DK_TGZ" "$Z88DK_URL"
        fi

        echo "Extracting z88dk source..."
        tar -xzf "$Z88DK_TGZ"
        if [ -d "z88dk-${Z88DK_NIGHTLY_ID}" ]; then
            mv "z88dk-${Z88DK_NIGHTLY_ID}" z88dk-src
        elif [ ! -d "z88dk-src" ]; then
            if [ -d "z88dk" ] && [ ! -d "z88dk-src" ]; then
                mv z88dk z88dk-src
            fi
        fi

        echo "Building z88dk host tools..."
        cd z88dk-src
        chmod +x build.sh
        ./build.sh -l

        echo "Installing z88dk..."
        mkdir -p ../z88dk
        make PREFIX="$(cd .. && pwd)/z88dk" install
        cp -R lib ../z88dk
        cp -R include ../z88dk
        cp -R support ../z88dk

        cd ..

        rm -rf z88dk-src
        rm -f "$Z88DK_TGZ"
    fi
    
    echo "z88dk installation complete!"
fi

# Install Python if not present
if [ "$OS" == "macos" ]; then
    if ! command -v python3 &> /dev/null; then
        echo "Installing Python via Homebrew..."
        if ! command -v brew &> /dev/null; then
            echo "Error: Homebrew not found. Please install Homebrew first: https://brew.sh"
            exit 1
        fi
        brew install python3
    else
        echo "Python3 already installed"
    fi
elif [ "$OS" == "ubuntu" ]; then
    if ! command -v python3 &> /dev/null; then
        echo "Installing Python via apt..."
        sudo apt-get update
        sudo apt-get install -y python3 python3-pip python3-venv
    else
        echo "Python3 already installed"
    fi
elif [ "$OS" == "alpine" ]; then
    if ! command -v python3 &> /dev/null; then
        echo "Installing Python via apk..."
        sudo apk add --no-cache python3 py3-pip py3-setuptools
    else
        echo "Python3 already installed"
    fi
fi

# Create Python venv if it doesn't exist (idempotent)
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
    echo "Virtual environment created!"
else
    echo "Virtual environment already exists, skipping creation..."
fi

# Install/upgrade Python dependencies
if [ -f "requirements.txt" ]; then
    echo "Installing Python dependencies..."
    source venv/bin/activate
    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
    deactivate
    echo "Python dependencies installed!"
else
    echo "Warning: requirements.txt not found, skipping dependency installation"
fi

echo ""
echo "Installation complete!"
echo ""
echo "To activate the SDK environment in this shell, run:"
echo "  source $SCRIPT_DIR/source.sh"
echo ""
echo "To automatically activate the SDK environment in new shells, add this to your shell config:"
echo ""
echo "For zsh (~/.zshrc):"
echo "  echo 'source $SCRIPT_DIR/source.sh' >> ~/.zshrc"
echo ""
echo "For bash (~/.bashrc):"
echo "  echo 'source $SCRIPT_DIR/source.sh' >> ~/.bashrc"
echo ""
