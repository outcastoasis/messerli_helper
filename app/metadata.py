"""Central application metadata used by runtime and packaging."""

APP_NAME = "Messerli Helper"
APP_EXECUTABLE_NAME = "MesserliHelper"
APP_EXECUTABLE_FILENAME = f"{APP_EXECUTABLE_NAME}.exe"
APP_INSTALL_DIR_NAME = "Messerli Helper"
APP_DATA_DIR_NAME = "MesserliHelper"

APP_PUBLISHER = "Jascha Bucher"
APP_PUBLISHER_ID = "JaschaBucher"
# Change the version only here.
APP_VERSION_PARTS = (0, 1, 4)
APP_VERSION = ".".join(str(part) for part in APP_VERSION_PARTS)
APP_VERSION_INFO = (*APP_VERSION_PARTS, 0)

APP_INSTALLER_APP_ID = f"{APP_PUBLISHER_ID}.{APP_EXECUTABLE_NAME}"
APP_USER_MODEL_ID = APP_INSTALLER_APP_ID
APP_INSTALLER_OUTPUT_NAME = f"{APP_EXECUTABLE_NAME}-Setup"
