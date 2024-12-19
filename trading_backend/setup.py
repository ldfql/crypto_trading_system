from setuptools import setup, find_packages

setup(
    name="crypto-trading-backend",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.109.0,<0.110.0",
        "sqlalchemy>=2.0.25,<3.0.0",
        "alembic>=1.13.1,<2.0.0",
        "psycopg2-binary>=2.9.9,<3.0.0",
        "pydantic>=2.5.3,<3.0.0",
        "pydantic-settings>=2.1.0,<3.0.0",
        "python-dotenv>=1.0.0,<2.0.0",
        "uvicorn>=0.25.0,<0.26.0",
        "transformers>=4.47.0",
        "torch>=2.2.1",
        "jieba>=0.42.1",
        "beautifulsoup4>=4.12.3",
        "aiohttp>=3.11.10",
        "pytest>=8.3.4",
        "pytest-asyncio>=0.25.0",
        "numpy>=2.2.0",
    ],
    python_requires=">=3.12",
)
