from setuptools import setup, find_packages

setup(
    name="flounder",
    version="1.0.0",
    description="A simulation trading module with Binance WebSocket support",
    author="Trading Team",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "websocket-client>=1.8.0",
        "matplotlib>=3.7.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "flounder=main:main",
        ]
    },
    python_requires=">=3.8",
)