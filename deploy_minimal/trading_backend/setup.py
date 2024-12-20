from setuptools import setup, find_packages

setup(
    name="crypto_trading_system",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "sqlalchemy",
        "pydantic",
        "pytest",
        "pytest-asyncio",
        "pytest-mock",
        "aiohttp",
        "python-dotenv",
        "alembic",
    ],
    extras_require={
        "dev": [
            "pytest",
            "pytest-asyncio",
            "pytest-mock",
            "pytest-cov",
        ]
    }
)
