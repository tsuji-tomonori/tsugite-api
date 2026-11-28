// 初期担当者と個人ユーザーの二人について、管理者ロールの引き継ぎを検査する。
module administrators {
  var first: bool
  var second: bool
  var caller: str
  var target: str
  var grant: bool
  var response: int
  action init = all { first' = true, second' = false, caller' = "", target' = "", grant' = false, response' = 0 }
  action change(by: str, who: str, enable: bool): bool = {
    val allowed = if (by == "first") first else second
    val other = if (who == "first") second else first
    val code = if (not(allowed)) 403 else if (not(enable) and not(other)) 409 else 200
    all { caller' = by, target' = who, grant' = enable, response' = code,
          first' = if (code == 200 and who == "first") enable else first,
          second' = if (code == 200 and who == "second") enable else second }
  }
  action step = {
    nondet by = Set("first", "second").oneOf()
    nondet who = Set("first", "second").oneOf()
    nondet enable = Bool.oneOf()
    change(by, who, enable)
  }
  val safe = first or second
  run handoverTest = init.then(change("first", "first", false)).then(change("second", "second", true))
    .then(change("first", "second", true)).then(change("first", "second", true))
    .then(change("second", "first", false)).then(change("first", "second", false))
    .then(change("second", "second", false))
}
