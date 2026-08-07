import sys
import workflows
from ui.view_controller import bootstrap

try:
    import numpy, pandas, matplotlib, cv2, scipy, sklearn
    
except ModuleNotFoundError as exc:
    missing_name = exc.name or str(exc)
    print(
        f"Dependency missing: {missing_name}\n"
        "Please install required packages with:\n"
        "  pip install -r requirements.txt",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc


def main():
    app = bootstrap()
    app.mainloop()


if __name__ == "__main__":
    main()
