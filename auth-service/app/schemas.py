from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.cnpj import format_cnpj, is_valid_cnpj, normalize_cnpj

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class Role(str, Enum):
    CLIENTE = "CLIENTE"
    LOJISTA = "LOJISTA"


class CustomerRegister(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(max_length=254, pattern=EMAIL_PATTERN)
    password: str = Field(min_length=8, max_length=128)

    # mode="before": limpa o texto ANTES de conferir tamanho e formato.
    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("email", mode="before")
    @classmethod
    def lowercase_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class OwnerRegister(CustomerRegister):
    company_name: str = Field(min_length=2, max_length=100)
    cnpj: str

    @field_validator("cnpj")
    @classmethod
    def check_cnpj(cls, value: str) -> str:
        if not is_valid_cnpj(value):
            raise ValueError("CNPJ inválido")
        return normalize_cnpj(value)


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    role: Role
    company_name: str | None = None
    cnpj: str | None = None

    @field_validator("cnpj")
    @classmethod
    def show_formatted(cls, value: str | None) -> str | None:
        return format_cnpj(value) if value else value


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
