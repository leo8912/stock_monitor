from pathlib import Path


def load_global_stylesheet(font_family: str, font_size: int) -> str:
    """
    Load the global QSS stylesheet and inject dynamic variables.

    Args:
        font_family (str): Font family name.
        font_size (int): Font size in pixels.

    Returns:
        str: Parsed QSS stylesheet string.
    """
    styles_path = Path(__file__).parent.parent / "resources" / "styles" / "main.qss"
    if not styles_path.exists():
        return ""

    with open(styles_path, encoding="utf-8") as f:
        stylesheet = f.read()

    # Inject dynamic variables
    stylesheet = stylesheet.replace("{{FONT_FAMILY}}", font_family)
    stylesheet = stylesheet.replace("{{FONT_SIZE}}", str(font_size))

    return stylesheet
