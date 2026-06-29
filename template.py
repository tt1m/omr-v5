import json
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field
from enum import Enum

# cropping -> perspective warp -> deskewing -> resize
# gui: load image -> add sections -> users configure label, type, first_bubble, grid, rows, cols, row_gap, col_gap, bubble_dimensions, options

# ── Shared primitives ────────────────────────────────────────────
class BubbleShape(str, Enum):
    rectangle = "rectangle"
    circle = "circle"

class BubbleDimensions(BaseModel):
    shape: BubbleShape
    width: int = Field(gt=0)
    height: int = Field(gt=0)

class Bubble(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    value: str

class ImageDimensions(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)

# ── Entries (differ by field type) ───────────────────────────────
class MetadataEntry(BaseModel):
    name: str                    # e.g. "digit_1"
    bubbles: list[Bubble] = Field(min_length=1)

class AnswerEntry(BaseModel):
    question: int = Field(gt=0)  # 1-indexed question number
    bubbles: list[Bubble] = Field(min_length=2)  # at least A/B

# ── Fields (discriminated union on `type`) ────────────────────────
class MetadataField(BaseModel):
    name: str
    type: Literal["metadata"]
    bubble: BubbleDimensions
    entries: list[MetadataEntry] = Field(min_length=1)

class AnswersField(BaseModel):
    name: str
    type: Literal["answers"]
    bubble: BubbleDimensions
    entries: list[AnswerEntry] = Field(min_length=1)

AnyField = Annotated[
    Union[MetadataField, AnswersField],
    Field(discriminator="type")
]

# ── Root template ────────────────────────────────────────────────
class OMRTemplate(BaseModel):
    name: str
    image: ImageDimensions
    fields: list[AnyField] = Field(min_length=1)

print(OMRTemplate.model_json_schema())