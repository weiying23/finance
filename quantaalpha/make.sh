cd QuantaAlpha
# Install the package in development mode
SETUPTOOLS_SCM_PRETEND_VERSION=0.1.0 pip install -e .

# Install additional dependencies
pip install -r requirements.txt
