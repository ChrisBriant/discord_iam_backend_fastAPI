from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, declarative_base
import os,dotenv

# #LOAD ENVIRONMENT
dotenv_file = ".env"
if os.path.isfile(dotenv_file):
    dotenv.load_dotenv(dotenv_file)

#DB PARAMS
DB_NAME = os.environ.get("DB_NAME")
DB_USERNAME = os.environ.get("DB_USERNAME")
DB_PASSWORD = os.environ.get("DB_PASSWORD")

DATABASE_URL = f"postgresql+asyncpg://{DB_USERNAME}:{DB_PASSWORD}@localhost/{DB_NAME}"

engine = create_async_engine(DATABASE_URL, echo=False)

# Use async_sessionmaker instead of sessionmaker
SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False
)

Base = declarative_base()