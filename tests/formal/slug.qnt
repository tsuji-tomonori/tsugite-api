// 削除後も予約する識別名を一つ選び、作成・改名・削除・再登録を調べる。
module slug {
  var lifecycle: str
  var operation: str
  var response: int
  action record(op: str, stage: str, code: int): bool = all {
    operation' = op, lifecycle' = stage, response' = code
  }
  action init = all { operation' = "init", lifecycle' = "available", response' = 0 }
  action create = if (lifecycle == "available") record("create", "listed", 201)
                  else record("create", lifecycle, 409)
  action invalid = record("invalid", lifecycle, 422)
  action rename = all { lifecycle == "listed", record("rename", lifecycle, 409) }
  action remove = all { lifecycle == "listed", record("delete", "reserved", 200) }
  action step = any { create, invalid, rename, remove }
  val safe = (response == 201 implies lifecycle == "listed") and
             (operation == "delete" implies lifecycle == "reserved")
  run reservedTest = init.then(invalid).then(create).then(create).then(rename).then(remove).then(create)
}
