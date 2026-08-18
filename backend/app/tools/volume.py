"""Get or set system volume."""
import subprocess
from langchain_core.tools import tool
from app.core.logger import get_logger

logger = get_logger(__name__)


@tool
def change_volume(level: int) -> str:
    """Changes the system volume. The level must be an integer between 0 and 100."""
    logger.info(f"Changing volume to {level}%")
    try:
        subprocess.run(["amixer", "-D", "pulse", "sset", "Master", f"{level}%"], check=True)
        return f"Successfully set volume to {level}%."
    except Exception as e:
        logger.error(f"Failed to change volume: {e}")
        return f"Failed to set volume: {e}"
