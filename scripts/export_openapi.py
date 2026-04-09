from __future__ import annotations

import json
from pathlib import Path

from memory_engine.api.app import create_app
from memory_engine.config.settings import get_settings


def main() -> None:
    app = create_app()
    target = Path(get_settings().docs_export_openapi_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
