"""Central application metadata used by runtime and packaging."""

APP_NAME = "Messerli Helper"
APP_EXECUTABLE_NAME = "MesserliHelper"
APP_EXECUTABLE_FILENAME = f"{APP_EXECUTABLE_NAME}.exe"
APP_INSTALL_DIR_NAME = "Messerli Helper"
APP_DATA_DIR_NAME = "MesserliHelper"

APP_PUBLISHER = "Jascha Bucher"
APP_PUBLISHER_ID = "JaschaBucher"
# Change the version only here.
APP_VERSION_PARTS = (1, 0, 2)
APP_VERSION = ".".join(str(part) for part in APP_VERSION_PARTS)
APP_VERSION_INFO = (*APP_VERSION_PARTS, 0)
# Temporary testing switch. Set to False to show the tutorial only on first start.
APP_ALWAYS_SHOW_TUTORIAL_ON_START = False

APP_INSTALLER_APP_ID = f"{APP_PUBLISHER_ID}.{APP_EXECUTABLE_NAME}"
APP_USER_MODEL_ID = APP_INSTALLER_APP_ID
APP_INSTALLER_OUTPUT_NAME = f"{APP_EXECUTABLE_NAME}-Setup"
APP_GITHUB_OWNER = "outcastoasis"
APP_GITHUB_REPOSITORY = "messerli_helper"
APP_GITHUB_REPOSITORY_SLUG = f"{APP_GITHUB_OWNER}/{APP_GITHUB_REPOSITORY}"
APP_GITHUB_LATEST_RELEASE_API_URL = (
    f"https://api.github.com/repos/{APP_GITHUB_REPOSITORY_SLUG}/releases/latest"
)
APP_GITHUB_RELEASES_PAGE_URL = (
    f"https://github.com/{APP_GITHUB_REPOSITORY_SLUG}/releases"
)
APP_INSTALLER_FILENAME_PREFIX = f"{APP_INSTALLER_OUTPUT_NAME}-"
