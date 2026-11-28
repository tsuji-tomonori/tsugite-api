/// 利用者プロフィール
/// 氏名の登録状態、表示名、本人・管理者・第三者の更新権限、古い版による更新を扱う。
module profiles {
  var named: bool
  var hasFullName: bool
  var operation: str
  var response: int
  action init = all { named' = false, hasFullName' = false, operation' = "init", response' = 0 }
  action edit(op: str): bool = {
    val status = if (op == "other") 403 else if (op == "stale") 409
      else if (op == "clearFull" or (not(hasFullName) and op != "selfSet")) 422 else 200
    all {
      named' = if (status != 200) named else (op == "selfSet"),
      hasFullName' = (hasFullName or (op == "selfSet")),
      operation' = op, response' = status
    }
  }
  action step = any { edit("selfSet"), edit("adminClear"), edit("other"), edit("clearFull"),
    all { hasFullName, edit("stale") } }
  /// 第三者の更新は403、氏名の消去は422で拒否し、更新成功後は氏名が登録されている。
  val safe = and { (operation == "other") implies response == 403,
    (operation == "clearFull") implies response == 422, (response == 200) implies hasFullName }
  run profileTest = init.then(edit("selfSet")).then(edit("other")).then(edit("stale")).then(edit("adminClear"))
  run requiredFullNameTest = init.then(edit("adminClear")).then(edit("selfSet")).then(edit("clearFull"))
}
