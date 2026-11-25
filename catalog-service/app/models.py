"""Tabelas do banco: restaurantes e seus produtos (relação 1 para N)."""
from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Restaurant(Base):
    __tablename__ = "restaurants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    category: Mapped[str] = mapped_column(String(50))
    owner_id: Mapped[int] = mapped_column(index=True)  # id do lojista no Auth Service

    products: Mapped[list["Product"]] = relationship(
        back_populates="restaurant", cascade="all, delete-orphan"
    )


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    price: Mapped[float] = mapped_column(Float)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("restaurants.id"))

    restaurant: Mapped[Restaurant] = relationship(back_populates="products")

    # O Orders Service precisa saber de qual restaurante e de qual dono é o produto.
    @property
    def restaurant_name(self) -> str:
        return self.restaurant.name

    @property
    def owner_id(self) -> int:
        return self.restaurant.owner_id
