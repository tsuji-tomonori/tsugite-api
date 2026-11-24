from pydantic import Field

from app.schemas.base import Input


#: 利用者メタデータの項目設定
class MetadataSettings(Input):
    #: 画面に表示する項目名
    label: str = Field(min_length=1, max_length=120)
    #: 値の名称を全利用者に公開するか
    public_values: bool = False
