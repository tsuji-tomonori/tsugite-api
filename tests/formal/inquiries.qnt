/// 問い合わせの受付と回答
/// 一つの受付番号に対する送信・再送と、管理者や第三者による回答操作を扱う。
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
  /// 回答済みの問い合わせは、受付済みである。
  val safe = answered implies submitted
  run inquiryTest = init.then(submit).then(submit).then(otherReply).then(adminReply)
}
