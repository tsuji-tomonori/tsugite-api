// 固定した受付番号の再送と回答の閲覧者を扱う。
module inquiries {
  var operation: str
  var submitted: bool
  var answered: bool
  var response: int
  action result(op: str, sent: bool, reply: bool, code: int): bool = all {
    operation' = op, submitted' = sent, answered' = reply, response' = code
  }
  action init = all { answered' = false, operation' = "init", response' = 0, submitted' = false }
  action submit = result("submit", true, answered, 201)
  action otherReply = all { submitted, result("otherReply", true, answered, 403) }
  action adminReply = all { submitted, result("adminReply", true, true, 200) }
  action step = any { submit, otherReply, adminReply }
  val safe = answered implies submitted
  run inquiryTest = init.then(submit).then(submit).then(otherReply).then(adminReply)
}
