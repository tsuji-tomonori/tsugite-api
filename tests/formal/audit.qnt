/// アクセスログと監査
/// 本人画面と監査画面について、本人の呼び出しか、監査対象の範囲内か、現在の役割は何かによって応答を決める。
module audit {
  var role: str
  var view: str
  var own: bool
  var within: bool
  var response: int
  action read(asRole: str, page: str, mine: bool, led: bool): bool = all {
    role' = asRole, view' = page, own' = mine, within' = led,
    response' = if (page == "personal") (if (mine) 200 else 404)
                else if (asRole == "member") 403
                else if (asRole == "lead" and not(led)) 404 else 200
  }
  action init = all { own' = true, response' = 200, role' = "member", view' = "personal", within' = false }
  action step = {
    nondet r = Set("member", "lead", "admin", "auditor").oneOf()
    nondet p = Set("personal", "audit").oneOf()
    nondet mine = Bool.oneOf()
    nondet led = Bool.oneOf()
    read(r, p, mine, led)
  }
  /// 本人のアクセスログを取得できた場合、対象の呼び出しは本人のものである。
  val safe = (view == "personal" and response == 200) implies own
  run personalLogTest = init.then(read("member","personal",false,true))
    .then(read("admin","personal",false,true)).then(read("lead","personal",false,true))
  run auditLogTest = init.then(read("lead","audit",false,true)).then(read("lead","audit",false,false))
    .then(read("member","audit",false,true)).then(read("admin","audit",false,false))
    .then(read("auditor","audit",false,false))
}
