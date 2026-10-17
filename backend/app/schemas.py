from pydantic import BaseModel, Field, HttpUrl
from typing import Optional

class ProductCreate(BaseModel):
    url: HttpUrl
    target_price: Optional[float] = Field(default=None, gt=0)
    title: Optional[str] = Field(default=None, max_length=300)

class ProductUpdate(BaseModel):
    target_price: Optional[float] = Field(default=None, gt=0)
