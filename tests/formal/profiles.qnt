/// 利用者プロフィール
/// 本人、管理者、第三者による名前の更新と、古い版を使った更新を扱う。
module profiles {
  var named: bool
  var operation: str
  var response: int
  action init = all { named' = false, operation' = "init", response' = 0 }
  action edit(op: str): bool = all {
    named' = if (op == "selfSet") true else if (op == "adminClear") false else named,
    operation' = op, response' = if (op == "other") 403 else if (op == "stale") 409 else 200
  }
  action step = any { edit("selfSet"), edit("adminClear"), edit("other"), all { named, edit("stale") } }
  /// 第三者によるプロフィールの更新はHTTP 403で拒否される。
  val safe = (operation == "other") implies response == 403
  run profileTest = init.then(edit("selfSet")).then(edit("other")).then(edit("stale")).then(edit("adminClear"))
}
