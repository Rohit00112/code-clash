"""Run background submission worker as a standalone process."""

import logging
import time

from app.services.submission_worker import submission_worker


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    submission_worker.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        submission_worker.stop()


if __name__ == "__main__":
    main()
