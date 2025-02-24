from pydantic import BaseModel
from typing import Optional, Union
from typing import Optional
class GetFirRequest(BaseModel):
    police_station: str
    year: int
    district: str
    fir_number: str
    user_id: str

class DraftRequest(BaseModel):
    summary: str
    pdf_link: str

class DraftRequest(BaseModel):
    user_message: Union[str, None]
    session_id: str
    user_id: str

class SearchRequest(BaseModel):
    user_message: Union[str, None]
    session_id: str
    user_id: str

class UserDetailsRequest(BaseModel):
    user_id: str

class HistoryRequest(BaseModel):
    session_id: str
    user_id: str