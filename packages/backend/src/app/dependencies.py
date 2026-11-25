# 配布単位間のPython依存を構文木から検査する。
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session
from tsugite_db.session import session

from app.core.auth import Actor, human

DB = Annotated[Session, Depends(session)]


User = Annotated[Actor, Depends(human)]
