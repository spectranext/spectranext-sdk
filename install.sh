#!/bin/bash
set -e

# z88dk version to install
Z88DK_VERSION="2.3"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
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
        
        # Download z88dk binary release
        Z88DK_URL="https://github.com/z88dk/z88dk/releases/download/v${Z88DK_VERSION}/z88dk-osx-${Z88DK_VERSION}.zip"
        Z88DK_ZIP="z88dk-osx-${Z88DK_VERSION}.zip"
        
        if [ ! -f "$Z88DK_ZIP" ]; then
            echo "Downloading z88dk..."
            curl -L -o "$Z88DK_ZIP" "$Z88DK_URL"
        fi
        
        # Extract to z88dk folder
        echo "Extracting z88dk..."
        unzip -q -o "$Z88DK_ZIP" -d .
        # The zip might extract to a subdirectory, move contents if needed
        if [ -d "z88dk-osx-${Z88DK_VERSION}" ]; then
            mv "z88dk-osx-${Z88DK_VERSION}" z88dk
        fi
        
        # Clean up zip file
        rm -f "$Z88DK_ZIP"
        
    elif [ "$OS" == "linux" ]; then
        echo "Installing z88dk for Linux..."
        
        # Install build dependencies
        echo "Installing build dependencies..."
        sudo apt-get update
        sudo apt-get install -y \
            cmake git build-essential python3 python3-pip python3-venv \
            perl libxml2-dev m4 bison flex ragel dos2unix re2c \
            libjpeg-dev zlib1g-dev libgmp-dev \
            cpanminus
        
        # Install Perl modules
        echo "Installing Perl modules..."
        sudo cpanm -n Modern::Perl YAML::Tiny CPU::Z80::Assembler || {
            echo "Warning: Some Perl modules may have failed to install, continuing..."
        }
        
        # Download z88dk source release
        Z88DK_URL="https://github.com/z88dk/z88dk/releases/download/v${Z88DK_VERSION}/z88dk-src-${Z88DK_VERSION}.tgz"
        Z88DK_TGZ="z88dk-src-${Z88DK_VERSION}.tgz"
        
        if [ ! -f "$Z88DK_TGZ" ]; then
            echo "Downloading z88dk source..."
            curl -L -o "$Z88DK_TGZ" "$Z88DK_URL"
        fi
        
        # Extract to z88dk-src folder
        echo "Extracting z88dk source..."
        tar -xzf "$Z88DK_TGZ"
        # The tarball might extract to a subdirectory, move contents if needed
        if [ -d "z88dk-${Z88DK_VERSION}" ]; then
            mv "z88dk-${Z88DK_VERSION}" z88dk-src
        elif [ ! -d "z88dk-src" ]; then
            # If it extracted to current directory, rename it
            if [ -d "z88dk" ] && [ ! -d "z88dk-src" ]; then
                mv z88dk z88dk-src
            fi
        fi
        
        # Build z88dk
        echo "Building z88dk (this may take a while)..."
        cd z88dk-src
        chmod +x build.sh
        ./build.sh -p zx
        
        # Install to z88dk folder
        echo "Installing z88dk..."
        mkdir -p ../z88dk
        make PREFIX="$(cd .. && pwd)/z88dk" install
        
        cd ..
        
        # Clean up source and tarball
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
elif [ "$OS" == "linux" ]; then
    if ! command -v python3 &> /dev/null; then
        echo "Installing Python via apt..."
        sudo apt-get update
        sudo apt-get install -y python3 python3-pip python3-venv
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

# Install zmakebas
if [ -d "zmakebas" ] && [ -f "bin/zmakebas" ]; then
    echo "zmakebas already installed, skipping..."
else
    echo "Installing zmakebas..."
    
    # Check if git is available
    if ! command -v git &> /dev/null; then
        echo "Error: git is required to clone zmakebas. Please install git first."
        exit 1
    fi
    
    # Check if make is available
    if ! command -v make &> /dev/null; then
        echo "Error: make is required to build zmakebas. Please install make first."
        exit 1
    fi
    
    # Check if a C compiler is available
    if ! command -v gcc &> /dev/null && ! command -v clang &> /dev/null && ! command -v cc &> /dev/null; then
        echo "Error: A C compiler (gcc, clang, or cc) is required to build zmakebas. Please install a C compiler first."
        exit 1
    fi
    
    # Clone zmakebas repository
    if [ ! -d "zmakebas" ]; then
        echo "Cloning zmakebas repository..."
        git clone https://github.com/spectranext/zmakebas.git zmakebas
    fi
    
    # Build and install zmakebas
    cd zmakebas
    echo "Building zmakebas..."
    make
    
    echo "Installing zmakebas..."
    make PREFIX="$SCRIPT_DIR" install
    
    cd ..
    echo "zmakebas installation complete!"
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

