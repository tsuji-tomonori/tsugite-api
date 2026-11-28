/// 利用権の主体と呼び出し制限
/// 同じ商品、プロジェクト、環境について、利用権と呼び出し元の種別、利用停止やキー失効などの制限を扱う。
module entitlement {
  var scope: str
  var caller: str
  var gate: str
  var permitted: bool
  action check(right: str, who: str, restriction: str): bool = all {
    scope' = right, caller' = who, gate' = restriction,
    permitted' = (restriction == "open" and
      (right == "project" or (right == "personal" and who == "holder")))
  }
  action init = all { caller' = "holder", gate' = "open", permitted' = false, scope' = "absent" }
  action step = {
    nondet right = Set("absent", "project", "personal").oneOf()
    nondet who = Set("holder", "colleague", "machine", "shared").oneOf()
    nondet restriction = Set("open", "suspended", "stopped", "outside", "revokedKey").oneOf()
    check(right, who, restriction)
  }
  /// 呼び出しが許可されるには、利用権が存在し、呼び出しを妨げる制限が有効になっていないことが必要である。
  val safe = permitted implies gate == "open" and scope != "absent"
  run principalTest = init.then(check("personal","holder","open")).then(check("personal","colleague","open"))
    .then(check("personal","shared","open")).then(check("personal","machine","open"))
    .then(check("project","colleague","open")).then(check("project","machine","open"))
  run stopTest = init.then(check("project","holder","open")).then(check("project","holder","suspended"))
    .then(check("project","holder","stopped")).then(check("project","holder","outside"))
    .then(check("project","holder","revokedKey")).then(check("project","holder","open"))
}
