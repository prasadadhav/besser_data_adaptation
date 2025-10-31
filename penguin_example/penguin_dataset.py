import enum
from typing import List, Optional
from sqlalchemy import (
    create_engine, Column, ForeignKey, Table, Text, Boolean, String, Date, 
    Time, DateTime, Float, Integer, Enum
)
from sqlalchemy.orm import (
    column_property, DeclarativeBase, Mapped, mapped_column, relationship
)
from datetime import datetime, time, date

class Base(DeclarativeBase):
    pass



# Tables definition for many-to-many relationships
study_species = Table(
    "study_species",
    Base.metadata,
    Column("species", ForeignKey("species.id"), primary_key=True),
    Column("study", ForeignKey("study.id"), primary_key=True),
)

# Tables definition
class species(Base):
    __tablename__ = "species"
    id: Mapped[int] = mapped_column(primary_key=True)
    species_name: Mapped[str] = mapped_column(String(100))

class Study(Base):
    __tablename__ = "study"
    id: Mapped[int] = mapped_column(primary_key=True)
    study_number: Mapped[str] = mapped_column(String(100))
    island: Mapped[str] = mapped_column(String(100))
    region: Mapped[str] = mapped_column(String(100))

class Penguin(Base):
    __tablename__ = "penguin"
    id: Mapped[int] = mapped_column(primary_key=True)
    smaple_number: Mapped[int] = mapped_column(Integer)
    culmen_len: Mapped[float] = mapped_column(Float)
    culmen_depth: Mapped[float] = mapped_column(Float)
    flipper_len: Mapped[float] = mapped_column(Float)
    sex: Mapped[str] = mapped_column(String(100))
    egg: Mapped[bool] = mapped_column(Boolean)
    comments: Mapped[str] = mapped_column(String(100))
    individual_id: Mapped[str] = mapped_column(String(100))
    species_1_id: Mapped[int] = mapped_column(ForeignKey("species.id"), nullable=False)


#--- Relationships of the species table
species.penguin: Mapped[List["Penguin"]] = relationship("Penguin", back_populates="species_1", foreign_keys=[Penguin.species_1_id])
species.study: Mapped[List["Study"]] = relationship("Study", secondary=study_species, back_populates="species")

#--- Relationships of the study table
Study.species: Mapped[List["species"]] = relationship("species", secondary=study_species, back_populates="study")

#--- Relationships of the penguin table
Penguin.species_1: Mapped["species"] = relationship("species", back_populates="penguin", foreign_keys=[Penguin.species_1_id])

# Database connection
DATABASE_URL = "sqlite:///penguin_dataset.db"  # SQLite connection
engine = create_engine(DATABASE_URL, echo=True)

# Create tables in the database
Base.metadata.create_all(engine, checkfirst=True)