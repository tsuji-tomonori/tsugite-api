/// 公開申請の変更と再申請
/// 公開審査の却下、編集中断、取下げ、再申請後の旧審査への操作を扱う。
module publicationchanges {
  var pending: bool
  var operation: str
  var response: int
  action init = all { pending' = false, operation' = "init", response' = 0 }
  action submit = all { pending' = true, operation' = "submit", response' = 200 }
  action close(op: str): bool = all {
    pending, pending' = false, operation' = op, response' = 200
  }
  action oldDecision = all { pending' = pending, operation' = "stale", response' = 409 }
  action step = any { submit, close("reject"), close("edit"), close("withdraw"), oldDecision }
  /// 却下、編集、取下げの直後には、審査待ちの申請は残らない。
  val safe = Set("reject", "edit", "withdraw").contains(operation) implies not(pending)
  run restartTest = init.then(submit).then(close("reject")).then(submit).then(oldDecision)
    .then(close("edit")).then(oldDecision).then(submit).then(close("withdraw")).then(oldDecision)
}
