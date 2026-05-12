"""ORM setup."""
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, create_engine

Base = declarative_base()
engine = create_engine("sqlite:///app.db")
session = sessionmaker(bind=engine)()


class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    balance = Column(Integer)  # cents
