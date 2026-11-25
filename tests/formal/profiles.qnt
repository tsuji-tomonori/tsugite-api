// 本人と管理者だけが名前を変更でき、旧版での書き込みは状態を変えない。
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
  val safe = (operation == "other") implies response == 403
  run profileTest = init.then(edit("selfSet")).then(edit("other")).then(edit("stale")).then(edit("adminClear"))
}
