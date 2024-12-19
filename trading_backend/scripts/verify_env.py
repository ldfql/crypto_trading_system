"""Verify Python environment setup for sentiment analysis."""
import sys
import logging
import torch
import transformers
import datasets
import jieba
import numpy
import sklearn
import os
import psycopg2
from time import sleep
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def verify_cuda():
    """Verify CUDA availability and configuration."""
    if torch.cuda.is_available():
        device_count = torch.cuda.device_count()
        current_device = torch.cuda.current_device()
        device_name = torch.cuda.get_device_name(current_device)
        logger.info(f"CUDA available: {device_count} device(s)")
        logger.info(f"Current device: {current_device} - {device_name}")
        return True
    else:
        logger.warning("CUDA not available, using CPU")
        return False

def verify_model_dependencies():
    """Verify all required model dependencies are installed."""
    dependencies = {
        'Python': sys.version,
        'PyTorch': torch.__version__,
        'Transformers': transformers.__version__,
        'Datasets': datasets.__version__,
        'Jieba': jieba.__version__,
        'NumPy': numpy.__version__,
        'Scikit-learn': sklearn.__version__
    }

    for name, version in dependencies.items():
        logger.info(f"{name} version: {version}")

    return True

def verify_directories():
    """Verify required directories exist."""
    required_dirs = [
        'models',
        'logs',
        'results',
        'app/data'
    ]

    base_path = Path(__file__).parent.parent
    missing_dirs = []

    for dir_name in required_dirs:
        dir_path = base_path / dir_name
        if not dir_path.exists():
            missing_dirs.append(dir_name)
            logger.warning(f"Missing directory: {dir_path}")

    if missing_dirs:
        logger.error(f"Missing directories: {', '.join(missing_dirs)}")
        return False

    logger.info("All required directories present")
    return True

def verify_database():
    """Verify database connection."""
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL environment variable is not set")
        return False

    max_retries = 5
    retry_count = 0

    while retry_count < max_retries:
        try:
            conn = psycopg2.connect(db_url)
            conn.close()
            logger.info("Successfully connected to the database")
            return True
        except psycopg2.OperationalError as e:
            retry_count += 1
            if retry_count == max_retries:
                logger.error(f"Failed to connect to the database after {max_retries} retries: {str(e)}")
                return False
            logger.warning(f"Connection attempt {retry_count} failed, retrying in 2 seconds...")
            sleep(2)

def main():
    """Run all verification checks."""
    try:
        logger.info("Starting environment verification...")

        checks = [
            ('CUDA Configuration', verify_cuda),
            ('Model Dependencies', verify_model_dependencies),
            ('Directory Structure', verify_directories),
            ('Database Connection', verify_database)
        ]

        all_passed = True
        for name, check in checks:
            logger.info(f"\nVerifying {name}...")
            try:
                if not check():
                    all_passed = False
                    logger.error(f"{name} verification failed")
            except Exception as e:
                all_passed = False
                logger.error(f"Error during {name} verification: {str(e)}")

        if all_passed:
            logger.info("\nAll verification checks passed successfully!")
            return 0
        else:
            logger.error("\nSome verification checks failed")
            return 1

    except Exception as e:
        logger.error(f"Unexpected error during verification: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
