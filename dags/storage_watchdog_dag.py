import sys
sys.path.insert(0, "/root/letterboxd-movie-rec")

from datetime import datetime, timedelta

from airflow.decorators import dag, task
from dotenv import load_dotenv
from app_logger.app_logger import setup_logger

load_dotenv("/root/letterboxd-movie-rec/.env")

from database.mongodb_client import MongoDBClient

logger = setup_logger("/root/letterboxd-movie-rec/logs/storage_watchdog_dag.log", "StorageWatchdogDAG")

# Atlas free tier cap is 512 MB (total = storageSize + indexSize)
WARN_MB    = 400   # log a warning — start paying attention
CLEAN_MB   = 430   # trigger active cleanup
TARGET_MB  = 380   # stop cleaning once we're back under this
CAP_MB     = 512   # hard limit for reference

# How many documents to delete per cleanup pass
NO_SIGNAL_BATCH  = 10_000
OLDEST_BATCH     = 5_000
MAX_PASSES       = 10    # safety limit to avoid an infinite loop


default_args = {
    "owner": "DijkstraFTW",
    "start_date": datetime(2024, 1, 1),
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    "storage_watchdog_dag",
    default_args=default_args,
    schedule=None,   # triggered by letterboxd_bulk_scraping_dag after each run
    catchup=False,
    description="Monitor Atlas free-tier storage and prune old ratings when needed",
)
def storage_watchdog_dag():

    @task
    def check_storage() -> dict:
        """Read current DB size and decide whether cleanup is needed."""
        mongo = MongoDBClient()
        stats = mongo.get_db_size_mb()
        if not stats:
            raise RuntimeError("Could not retrieve DB size stats.")

        total_mb = stats["total_mb"]
        logger.info(
            f"Storage check — total: {total_mb:.1f} MB / {CAP_MB} MB  "
            f"(data: {stats['data_mb']:.1f}, storage: {stats['storage_mb']:.1f}, index: {stats['index_mb']:.1f})"
        )

        if total_mb >= WARN_MB:
            logger.warning(f"Storage at {total_mb:.1f} MB — approaching the {CAP_MB} MB cap.")
        if total_mb >= CLEAN_MB:
            logger.warning(f"Storage at {total_mb:.1f} MB — cleanup will run.")

        return {**stats, "needs_cleanup": total_mb >= CLEAN_MB}

    @task
    def cleanup_ratings(storage: dict):
        """
        Two-phase cleanup:
          Phase 1 — delete no-signal ratings (watched but never rated/liked/reviewed).
          Phase 2 — if still above TARGET_MB, delete oldest ratings in batches.
        Stops as soon as total_mb drops below TARGET_MB or MAX_PASSES is reached.
        """
        if not storage.get("needs_cleanup"):
            logger.info(f"Storage at {storage.get('total_mb', 0):.1f} MB — no cleanup needed.")
            return

        mongo = MongoDBClient()
        total_deleted = 0

        # --- Phase 1: no-signal entries ---
        logger.info("Phase 1: removing no-signal ratings (rating_val=0, not reviewed, not liked).")
        deleted = mongo.delete_no_signal_ratings(limit=NO_SIGNAL_BATCH)
        total_deleted += deleted
        logger.info(f"Phase 1 removed {deleted} documents.")

        # Re-check after phase 1
        stats = mongo.get_db_size_mb()
        logger.info(f"After phase 1: {stats.get('total_mb', 0):.1f} MB")

        # --- Phase 2: oldest-first ---
        passes = 0
        while stats.get("total_mb", 0) > TARGET_MB and passes < MAX_PASSES:
            passes += 1
            logger.info(
                f"Phase 2 pass {passes}/{MAX_PASSES}: "
                f"still at {stats['total_mb']:.1f} MB, deleting {OLDEST_BATCH} oldest ratings."
            )
            deleted = mongo.delete_oldest_ratings(limit=OLDEST_BATCH)
            total_deleted += deleted
            if deleted == 0:
                logger.warning("No more ratings to delete — stopping early.")
                break
            stats = mongo.get_db_size_mb()
            logger.info(f"After pass {passes}: {stats.get('total_mb', 0):.1f} MB")

        logger.info(
            f"Cleanup complete. Total deleted: {total_deleted}. "
            f"Final size: {stats.get('total_mb', 0):.1f} MB."
        )

    storage_stats = check_storage()
    cleanup_ratings(storage_stats)


storage_watchdog_dag = storage_watchdog_dag()
